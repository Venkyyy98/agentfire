import json,pytest
from providers.nimble import NimbleProvider,NimbleNotConfigured
class R:
 def __enter__(self):return self
 def __exit__(self,*_):pass
 def read(self):return json.dumps({'results':[{'title':'Pool docs','url':'https://example.com','description':'Pool exhaustion causes timeouts.'}]}).encode()
def test_nimble_not_configured(monkeypatch):
 monkeypatch.delenv('NIMBLE_API_KEY',raising=False)
 with pytest.raises(NimbleNotConfigured):NimbleProvider(api_key='')
def test_nimble_is_scenario_only(monkeypatch):
 monkeypatch.setattr('providers.nimble.urlopen',lambda *_a,**_k:R());assert 'never supplied' in NimbleProvider(api_key='x').search_pattern('pool')['scenario_relevance']
