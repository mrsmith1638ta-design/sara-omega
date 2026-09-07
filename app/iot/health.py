from __future__ import annotations
from statistics import mean,median
from .models import DeviceHealth,EvidenceClass
class DeviceHealthEngine:
    def __init__(self,store): self.store=store
    def evaluate(self,device_id):
        d=self.store.get_device(device_id)
        if d is None: raise KeyError('device_not_found')
        events=list(reversed(self.store.recent_telemetry(device_id,limit=200))); by={}
        for e in events:
            for k,v in e.metrics.items():
                if k in d.metric_allowlist: by.setdefault(k,[]).append(v)
        obs={}; anomalies=[]; evidence=[]
        for k,vals in by.items():
            nums=[float(v) for v in vals if isinstance(v,(int,float)) and not isinstance(v,bool)]
            if nums:
                cur=nums[-1]; base=median(nums[:-1] or nums); slope=(nums[-1]-nums[0])/max(1,len(nums)-1); obs[k]={'current':cur,'baseline_median':base,'mean':mean(nums),'trend_per_sample':slope,'samples':len(nums)}
                if len(nums)>=3 and (abs(cur-base)/max(abs(base),1)>=.15 or abs(slope)>=max(.5,abs(base)*.03)):
                    a={'metric':k,'kind':'drift','relative_drift':abs(cur-base)/max(abs(base),1),'trend_per_sample':slope}; anomalies.append(a); evidence.append(k); self.store.record_anomaly(device_id,a)
            elif vals: obs[k]={'current':vals[-1],'samples':len(vals)}
        cls=EvidenceClass.SUPPORTED if anomalies else (EvidenceClass.OBSERVED if obs else EvidenceClass.UNVERIFIED)
        return DeviceHealth(device_id=device_id,classification=cls,observations=obs,evidence_metrics=sorted(set(evidence)),anomalies=anomalies,root_cause_verified=False)
def truth_check_device_claim(claim,health):
    low=claim.lower(); over=any(x in low for x in ('has failed','is broken','hardware failure','battery failure','defective','root cause is')) and not health.root_cause_verified
    return {'allowed':not over,'status':'INSUFFICIENT_EVIDENCE' if over else health.classification.value,'fail_closed':over,'reason':'sensor observations do not independently verify physical root cause' if over else None,'certainty_ceiling':'SUPPORTED' if health.classification==EvidenceClass.SUPPORTED else health.classification.value}
