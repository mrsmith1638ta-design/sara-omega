from __future__ import annotations
import hashlib, json, os, secrets, sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .models import CommandRecord, CommandStatus, DeviceRecord, TelemetryEvent

def _iso(v:datetime|str|None=None)->str:
    if isinstance(v,str): return v
    return (v or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()

class IoTStore:
    def __init__(self, db_path:Path):
        self.db_path=db_path; self.db_path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.max_events_per_device=max(10,min(int(os.getenv('SARA_IOT_MAX_EVENTS_PER_DEVICE','5000')),100000)); self._initialize()
    @classmethod
    def from_env(cls): return cls(Path(os.getenv('SARA_DATA_DIR','./data')).expanduser()/'sara_iot.db')
    def close(self): return None
    def _connect(self):
        c=sqlite3.connect(self.db_path,timeout=10.0); c.row_factory=sqlite3.Row
        c.execute('PRAGMA busy_timeout=10000'); c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA synchronous=FULL'); return c
    def _initialize(self):
        with closing(self._connect()) as c:
            with c:
                c.executescript('''
CREATE TABLE IF NOT EXISTS devices(device_id TEXT PRIMARY KEY,record_json TEXT NOT NULL,secret_salt TEXT NOT NULL,secret_hash TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS telemetry_events(event_id TEXT PRIMARY KEY,device_id TEXT NOT NULL,message_id TEXT NOT NULL,event_timestamp TEXT NOT NULL,received_at TEXT NOT NULL,transport TEXT NOT NULL,topic TEXT NOT NULL,metrics_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_iot_telemetry_device_received ON telemetry_events(device_id,received_at DESC);
CREATE TABLE IF NOT EXISTS replay_ids(device_id TEXT NOT NULL,message_id TEXT NOT NULL,observed_at TEXT NOT NULL,PRIMARY KEY(device_id,message_id));
CREATE TABLE IF NOT EXISTS commands(command_id TEXT PRIMARY KEY,device_id TEXT NOT NULL,request_hash TEXT NOT NULL,record_json TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS health_baselines(device_id TEXT NOT NULL,metric TEXT NOT NULL,baseline_json TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(device_id,metric));
CREATE TABLE IF NOT EXISTS anomalies(anomaly_id INTEGER PRIMARY KEY AUTOINCREMENT,device_id TEXT NOT NULL,detail_json TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS quarantine_events(id INTEGER PRIMARY KEY AUTOINCREMENT,device_id TEXT NOT NULL,kind TEXT NOT NULL,created_at TEXT NOT NULL,quarantine_until TEXT);
CREATE TABLE IF NOT EXISTS pairing_codes(id TEXT PRIMARY KEY,code_salt TEXT NOT NULL,code_hash TEXT NOT NULL,device_class TEXT NOT NULL,model_prefix TEXT,expires_at TEXT NOT NULL,consumed_at TEXT,created_at TEXT NOT NULL);
''')
        try: os.chmod(self.db_path,0o600)
        except OSError: pass
    @staticmethod
    def _hash_secret(secret,salt_hex): return hashlib.pbkdf2_hmac('sha256',secret.encode(),bytes.fromhex(salt_hex),200000).hex()
    @staticmethod
    def _normalize_pairing_code(code): return ''.join(ch for ch in str(code).upper() if ch.isalnum())
    def register_device(self,record:DeviceRecord,telemetry_secret:str|None=None)->DeviceRecord:
        now=_iso()
        with closing(self._connect()) as c:
            existing=c.execute('SELECT secret_salt,secret_hash FROM devices WHERE device_id=?',(record.device_id,)).fetchone()
            if existing: salt,digest=existing['secret_salt'],existing['secret_hash']
            else:
                if not telemetry_secret or len(telemetry_secret)<24: raise ValueError('telemetry_secret_required_for_new_device')
                salt=secrets.token_hex(16); digest=self._hash_secret(telemetry_secret,salt)
            if telemetry_secret and existing: salt=secrets.token_hex(16); digest=self._hash_secret(telemetry_secret,salt)
            with c:
                c.execute('''INSERT INTO devices VALUES(?,?,?,?,?,?) ON CONFLICT(device_id) DO UPDATE SET record_json=excluded.record_json,secret_salt=excluded.secret_salt,secret_hash=excluded.secret_hash,updated_at=excluded.updated_at''',(record.device_id,record.model_dump_json(),salt,digest,now,now))
        return record
    def verify_device_secret(self,device_id,supplied):
        import hmac
        with closing(self._connect()) as c: row=c.execute('SELECT secret_salt,secret_hash FROM devices WHERE device_id=?',(device_id,)).fetchone()
        return bool(row and supplied and hmac.compare_digest(self._hash_secret(supplied,row['secret_salt']),row['secret_hash']))
    def get_device(self,device_id):
        with closing(self._connect()) as c: row=c.execute('SELECT record_json FROM devices WHERE device_id=?',(device_id,)).fetchone()
        return DeviceRecord.model_validate_json(row['record_json']) if row else None
    def list_devices(self):
        with closing(self._connect()) as c: rows=c.execute('SELECT record_json FROM devices ORDER BY device_id').fetchall()
        return [DeviceRecord.model_validate_json(r['record_json']) for r in rows]
    def record_telemetry(self,event:TelemetryEvent):
        with closing(self._connect()) as c:
            with c:
                c.execute('INSERT INTO telemetry_events VALUES(?,?,?,?,?,?,?,?)',(event.event_id,event.device_id,event.message_id,_iso(event.event_timestamp),_iso(event.received_at),event.transport,event.topic,json.dumps(event.metrics,sort_keys=True,separators=(',',':'))))
                c.execute('''DELETE FROM telemetry_events WHERE device_id=? AND event_id NOT IN (SELECT event_id FROM telemetry_events WHERE device_id=? ORDER BY received_at DESC,event_id DESC LIMIT ?)''',(event.device_id,event.device_id,self.max_events_per_device))
    def recent_telemetry(self,device_id,metric=None,limit=200):
        limit=max(1,min(int(limit),1000))
        with closing(self._connect()) as c: rows=c.execute('SELECT * FROM telemetry_events WHERE device_id=? ORDER BY received_at DESC,event_id DESC LIMIT ?',(device_id,limit)).fetchall()
        out=[]
        for r in rows:
            m=json.loads(r['metrics_json'])
            if metric is not None and metric not in m: continue
            out.append(TelemetryEvent(event_id=r['event_id'],device_id=r['device_id'],message_id=r['message_id'],event_timestamp=datetime.fromisoformat(r['event_timestamp']),received_at=datetime.fromisoformat(r['received_at']),transport=r['transport'],topic=r['topic'],metrics=m))
        return out
    def reserve_replay(self,device_id,message_id,observed_at):
        try:
            with closing(self._connect()) as c:
                with c: c.execute('INSERT INTO replay_ids VALUES(?,?,?)',(device_id,message_id,observed_at))
            return True
        except sqlite3.IntegrityError: return False
    def recent_replay_count(self,device_id,cutoff_iso):
        with closing(self._connect()) as c: r=c.execute('SELECT COUNT(*) n FROM replay_ids WHERE device_id=? AND observed_at>=?',(device_id,cutoff_iso)).fetchone()
        return int(r['n'])
    def record_failure(self,device_id,kind,quarantine_until=None):
        with closing(self._connect()) as c:
            with c: c.execute('INSERT INTO quarantine_events(device_id,kind,created_at,quarantine_until) VALUES(?,?,?,?)',(device_id,kind[:64],_iso(),quarantine_until))
    def failure_count(self,device_id,cutoff_iso):
        with closing(self._connect()) as c: r=c.execute('SELECT COUNT(*) n FROM quarantine_events WHERE device_id=? AND created_at>=?',(device_id,cutoff_iso)).fetchone()
        return int(r['n'])
    def quarantine_until(self,device_id):
        with closing(self._connect()) as c: r=c.execute('SELECT quarantine_until FROM quarantine_events WHERE device_id=? AND quarantine_until IS NOT NULL ORDER BY id DESC LIMIT 1',(device_id,)).fetchone()
        return datetime.fromisoformat(r['quarantine_until']) if r and r['quarantine_until'] else None
    def reserve_command(self,record:CommandRecord):
        with closing(self._connect()) as c:
            old=c.execute('SELECT request_hash,record_json FROM commands WHERE command_id=?',(record.command_id,)).fetchone()
            if old:
                if old['request_hash']!=record.request_hash: raise ValueError('command_id_reused_for_different_request')
                return CommandRecord.model_validate_json(old['record_json'])
            with c: c.execute('INSERT INTO commands VALUES(?,?,?,?,?,?,?)',(record.command_id,record.device_id,record.request_hash,record.model_dump_json(),record.status.value,_iso(record.created_at),_iso(record.updated_at)))
        return record
    def get_command(self,command_id):
        with closing(self._connect()) as c: r=c.execute('SELECT record_json FROM commands WHERE command_id=?',(command_id,)).fetchone()
        return CommandRecord.model_validate_json(r['record_json']) if r else None
    def update_command(self,command_id,status:CommandStatus,result:dict[str,Any]|None):
        cur=self.get_command(command_id)
        if cur is None: raise KeyError('command_not_found')
        up=cur.model_copy(update={'status':status,'result':result,'updated_at':datetime.now(timezone.utc)})
        with closing(self._connect()) as c:
            with c: c.execute('UPDATE commands SET status=?,record_json=?,updated_at=? WHERE command_id=?',(status.value,up.model_dump_json(),_iso(up.updated_at),command_id))
        return up
    def pending_commands_for_device(self,device_id,limit=10):
        limit=max(1,min(int(limit),10))
        with closing(self._connect()) as c:
            rows=c.execute("SELECT record_json FROM commands WHERE device_id=? AND status=? ORDER BY created_at ASC LIMIT ?",(device_id,CommandStatus.RESERVED.value,limit)).fetchall()
        return [CommandRecord.model_validate_json(r['record_json']) for r in rows]
    def acknowledge_device_command(self,device_id,command_id,status:CommandStatus,result):
        if status not in {CommandStatus.COMPLETED,CommandStatus.REJECTED,CommandStatus.SUBMISSION_UNVERIFIED}: raise ValueError('invalid_device_ack_status')
        cur=self.get_command(command_id)
        if cur is None or cur.device_id!=device_id: raise KeyError('command_not_found')
        if cur.status!=CommandStatus.RESERVED: raise ValueError('command_not_acknowledgeable')
        return self.update_command(command_id,status,result)
    def create_pairing_code(self,code,device_class,model_prefix,expires_at):
        normalized=self._normalize_pairing_code(code); salt=secrets.token_hex(16); digest=self._hash_secret(normalized,salt); now=_iso()
        with closing(self._connect()) as c:
            with c: c.execute('INSERT INTO pairing_codes VALUES(?,?,?,?,?,?,?,?)',(secrets.token_hex(16),salt,digest,device_class,model_prefix,_iso(expires_at),None,now))
    def consume_pairing_code(self,code,model):
        import hmac
        normalized=self._normalize_pairing_code(code); now=datetime.now(timezone.utc)
        with closing(self._connect()) as c:
            c.execute('BEGIN IMMEDIATE')
            rows=c.execute('SELECT * FROM pairing_codes WHERE consumed_at IS NULL AND expires_at>=? ORDER BY created_at DESC',(_iso(now),)).fetchall()
            match=None
            for row in rows:
                if hmac.compare_digest(self._hash_secret(normalized,row['code_salt']),row['code_hash']):
                    prefix=row['model_prefix']
                    if prefix and not model.startswith(prefix): break
                    match=row; break
            if match is None:
                c.rollback(); return None
            changed=c.execute('UPDATE pairing_codes SET consumed_at=? WHERE id=? AND consumed_at IS NULL',(_iso(now),match['id'])).rowcount
            if changed!=1:
                c.rollback(); return None
            c.commit(); return {'device_class':match['device_class'],'model_prefix':match['model_prefix']}
    def record_anomaly(self,device_id,detail):
        with closing(self._connect()) as c:
            with c: c.execute('INSERT INTO anomalies(device_id,detail_json,created_at) VALUES(?,?,?)',(device_id,json.dumps(detail,sort_keys=True,separators=(',',':')),_iso()))
