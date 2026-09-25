from dotenv import load_dotenv
load_dotenv()
import json
from events import EventStore
from providers.nimble import NimbleProvider,NimbleNotConfigured,NimbleError
from providers.rawtree import RawTreeEventBackend
try:
 n=NimbleProvider();record=n.search_pattern('database connection pool exhaustion production incident symptoms timeout acquiring connection');b=RawTreeEventBackend();e=EventStore(backend=b,agent_mode='scenario_intelligence',provider_mode='rawtree');e.record('design-time','nimble_scenario_intelligence_retrieved',**record);e.flush();print(json.dumps({'nimble_status':n.status.__dict__,'record':record,'run_id':e.run_id},indent=2))
except NimbleNotConfigured as x:print(json.dumps({'nimble_status':'NOT_CONFIGURED','detail':str(x)}))
except NimbleError as x:print(json.dumps({'nimble_status':'ERROR','detail':str(x)}))
