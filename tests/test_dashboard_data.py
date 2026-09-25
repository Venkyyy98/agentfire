from pathlib import Path

from dashboard_data import build_dashboard_data
class B:
 def query_run_events(self,_):return [{"event_type":"evaluation_corrected","payload_json":'{"pass":true,"memory_effect":"CORRECTLY_REJECTED"}'}]
 def query_similar_experiences(self,*_):return [{"memory_id":"MEM-7daaf5ef70cf","root_cause":"auth"}]
def test_dashboard_serializes_replay_data():
 d=build_dashboard_data(B());assert d['runs']['regression']['verdict']['pass'] is True;assert d['memory']['memory_id']=='MEM-7daaf5ef70cf';assert d['data_source']=='RAWTREE_LIVE'

def test_dashboard_contains_interactive_demo_controls():
 html=Path(__file__).parents[1].joinpath('dashboard.html').read_text()
 for label in ('Start endurance test','TEST','REPLAY','REPORT','PROVIDERS','Pause','2×','Skip to next incident'):
  assert label in html

def test_verified_cache_is_explicitly_labeled():
 from verified_replay_cache import CACHE
 assert CACHE['data_source']=='VERIFIED_CACHED_REPLAY'
 assert CACHE['runs']['incident_1']['id']=='RUN-cbc2e587b04f'
 assert CACHE['runs']['baseline']['verdict']['memory_effect']=='MISLED'
 assert CACHE['runs']['regression']['verdict']['memory_effect']=='CORRECTLY_REJECTED'
