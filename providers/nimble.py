"""Nimble Search scenario intelligence; never passed to the agent under test."""
from __future__ import annotations
import json, os
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
class NimbleError(RuntimeError): pass
class NimbleNotConfigured(NimbleError): pass
@dataclass(frozen=True)
class ProviderStatus: state:str; detail:str
class NimbleProvider:
 def __init__(self,api_key=None,base_url=None):
  self.api_key=api_key or os.getenv('NIMBLE_API_KEY','');self.base_url=base_url or os.getenv('NIMBLE_API_URL','https://sdk.nimbleway.com/v2/search');self._status=ProviderStatus('NOT_CONFIGURED','NIMBLE_API_KEY is missing') if not self.api_key else ProviderStatus('ERROR','Not yet authenticated')
  if not self.api_key: raise NimbleNotConfigured('Nimble scenario intelligence requires NIMBLE_API_KEY')
 @property
 def status(self): return self._status
 def search_pattern(self,query):
  req=Request(self.base_url,data=json.dumps({'query':query,'max_results':1,'search_depth':'standard'}).encode(),method='POST',headers={'Authorization':f'Bearer {self.api_key}','Content-Type':'application/json'})
  try:
   with urlopen(req,timeout=45) as r:data=json.loads(r.read().decode())
  except HTTPError as e:self._status=ProviderStatus('ERROR',f'Nimble HTTP {e.code}');raise NimbleError(f'Nimble HTTP {e.code}') from e
  except URLError as e:self._status=ProviderStatus('ERROR',f'Nimble connection failed: {e.reason}');raise NimbleError(f'Nimble connection failed: {e.reason}') from e
  results=data.get('results') or []
  if not results:raise NimbleError('Nimble returned no scenario-intelligence results')
  x=results[0];self._status=ProviderStatus('CONNECTED','Authenticated Nimble Search retrieval succeeded')
  return {'source_provider':'nimble','query':query,'source_title':x.get('title','Untitled'),'source_url':x.get('url',''),'extracted_pattern':(x.get('description') or x.get('content') or '')[:400],'scenario_relevance':'Used to ground AgentFire fire-drill design; never supplied to the agent under test.','retrieved_at':datetime.now(timezone.utc).isoformat()}
