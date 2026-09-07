from __future__ import annotations
import hmac,os
from fastapi import APIRouter,Header,HTTPException
from pydantic import BaseModel,Field
from .models import DeviceRegistrationRequest,IoTError,TelemetryEnvelope
from .service import IoTService
router=APIRouter(); service=IoTService()
class PrepareCommandRequest(BaseModel):
    action:str=Field(min_length=1,max_length=96); parameters:dict=Field(default_factory=dict,max_length=32); session_id:str=Field(min_length=1,max_length=160); requested_by:str=Field(default='owner',min_length=1,max_length=128)
class ExecuteCommandRequest(BaseModel):
    command_id:str=Field(min_length=8,max_length=160); confirmation_token:str|None=Field(default=None,max_length=512)
def _bearer(auth): return auth[7:].strip() if auth and auth.startswith('Bearer ') else ''
def _require_exact_env(auth,env_name,forbidden=()):
    supplied=_bearer(auth); expected=os.getenv(env_name,'').strip(); bad={os.getenv(x,'').strip() for x in forbidden}; bad.discard('')
    if not expected or expected in bad or not supplied or supplied in bad or not hmac.compare_digest(expected,supplied): raise HTTPException(status_code=403,detail='authority_rejected')
    return supplied
def _require_user(auth):
    supplied=_bearer(auth); allowed=[os.getenv('OWNER_TOKEN','').strip(),os.getenv('GPT_ACTION_TOKEN','').strip()]
    if not supplied or not any(v and hmac.compare_digest(v,supplied) for v in allowed): raise HTTPException(status_code=401,detail='authentication_required')
@router.get('/iot/health')
async def iot_health(): return service.health()
@router.post('/iot/devices/register')
async def register_device(request:DeviceRegistrationRequest,authorization:str|None=Header(default=None)):
    _require_exact_env(authorization,'SARA_DEVICE_CONTROL_AUTH_TOKEN',('OWNER_TOKEN','GPT_ACTION_TOKEN','TEST_TOKEN','SARA_RAILWAY_CONTROL_AUTH_TOKEN','SARA_SOURCE_CONTROL_AUTH_TOKEN'))
    try: return service.register_device(request.device,request.telemetry_secret)
    except (ValueError,IoTError) as e: raise HTTPException(status_code=400,detail=str(e)) from e
@router.get('/iot/devices')
async def list_devices(authorization:str|None=Header(default=None)):
    _require_user(authorization); return {'devices':service.store.list_devices()}
@router.get('/iot/devices/{device_id}')
async def get_device(device_id:str,authorization:str|None=Header(default=None)):
    _require_user(authorization); d=service.store.get_device(device_id)
    if d is None: raise HTTPException(status_code=404,detail='device_not_found')
    return d
@router.post('/iot/telemetry')
async def ingest_telemetry(envelope:TelemetryEnvelope,x_sara_device_secret:str|None=Header(default=None),x_sara_iot_transport:str=Header(default='https')):
    try: return service.ingest_telemetry(envelope,x_sara_device_secret or '',x_sara_iot_transport.lower())
    except IoTError as e: raise HTTPException(status_code=403,detail=str(e)) from e
    except ValueError as e: raise HTTPException(status_code=400,detail=str(e)) from e
@router.get('/iot/devices/{device_id}/health')
async def device_health(device_id:str,authorization:str|None=Header(default=None)):
    _require_user(authorization)
    try: return service.device_health(device_id)
    except KeyError as e: raise HTTPException(status_code=404,detail='device_not_found') from e
@router.post('/iot/devices/{device_id}/commands/prepare')
async def prepare_command(device_id:str,request:PrepareCommandRequest,authorization:str|None=Header(default=None)):
    _require_user(authorization)
    try: return service.prepare_command(device_id,request.action,request.parameters,request.session_id,request.requested_by)
    except IoTError as e: raise HTTPException(status_code=422,detail=str(e)) from e
@router.post('/iot/devices/{device_id}/commands/execute')
async def execute_command(device_id:str,request:ExecuteCommandRequest,authorization:str|None=Header(default=None)):
    token=_require_exact_env(authorization,'SARA_DEVICE_CONTROL_AUTH_TOKEN',('OWNER_TOKEN','GPT_ACTION_TOKEN','TEST_TOKEN','SARA_RAILWAY_CONTROL_AUTH_TOKEN','SARA_SOURCE_CONTROL_AUTH_TOKEN')); existing=service.get_command(request.command_id)
    if existing is None or existing.device_id!=device_id: raise HTTPException(status_code=404,detail='command_not_found')
    try: return service.execute_command(request.command_id,token,request.confirmation_token)
    except IoTError as e: raise HTTPException(status_code=409,detail=str(e)) from e
    except (ValueError,PermissionError) as e: raise HTTPException(status_code=422,detail=str(e)) from e
@router.get('/iot/devices/{device_id}/commands/{command_id}')
async def get_command(device_id:str,command_id:str,authorization:str|None=Header(default=None)):
    _require_user(authorization); c=service.get_command(command_id)
    if c is None or c.device_id!=device_id: raise HTTPException(status_code=404,detail='command_not_found')
    return c
