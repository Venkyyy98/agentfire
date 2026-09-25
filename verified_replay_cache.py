"""Minimal cache derived from previously verified RawTree telemetry; never synthetic demo events."""
CACHE = {
 "data_source":"VERIFIED_CACHED_REPLAY",
 "providers":{"openai":"CONNECTED","rawtree":"TEMPORARILY_UNAVAILABLE","liquid":"CONNECTED","nimble":"CONNECTED"},
 "health":{"payment":"healthy","checkout":"healthy","auth":"healthy","database":"recovered","queue":"not observed"},
 "context":{"raw_event_count":71,"raw_history_bytes":52501,"estimated_raw_tokens":13125,"durable_memory_bytes":1464,"estimated_durable_memory_tokens":366},
 "memory":{"memory_id":"MEM-7daaf5ef70cf","root_cause":"Authentication credential expiration caused upstream authentication failures, degrading payment and checkout services.","successful_fix":["refresh_credentials:auth - successfully refreshed auth credentials"],"reusable_lesson":"Authentication credential expiration may cause cascading service degradation.","do_not_assume":"Verify current authentication health before reusing remediation."},
 "nimble_record":{"query":"database connection pool exhaustion production incident symptoms timeout acquiring connection","source_title":"Unmask Connection Pool Issues & Boost Performance","source_url":"https://www.radview.com/blog/connection-pool-exhaustion-detect-diagnose-fix/","extracted_pattern":"Connection-pool exhaustion can present as rising latency, errors, and timeouts while other infrastructure metrics appear normal."},
 "runs":{
  "incident_1":{"id":"RUN-cbc2e587b04f","events":71,"verdict":{"status":"passed"},"replay":[
   {"tool":"get_metrics","service":"payment","result":{"status":"degraded","error_rate":0.72,"latency":820}},
   {"tool":"get_metrics","service":"checkout","result":{"status":"degraded","error_rate":0.72,"latency":820}},
   {"tool":"get_metrics","service":"auth","result":{"status":"degraded","token_valid":False}},
   {"tool":"get_logs","service":"auth","result":["TOKEN_EXPIRED: shared credential rejected"]},
   {"tool":"refresh_credentials","service":"auth","result":{"recovered":True,"result":"credentials_refreshed"}},
   {"tool":"verify_service","service":"payment","result":{"healthy":True,"status":"healthy"}},
   {"tool":"verify_service","service":"checkout","result":{"healthy":True,"status":"healthy"}}]},
  "baseline":{"id":"RUN-af7d03cf281c","events":75,"verdict":{"status":"failed","memory_effect":"MISLED","unnecessary_action_count":1},"replay":[
   {"tool":"get_metrics","service":"auth","result":{"status":"healthy","token_valid":True}},
   {"tool":"refresh_credentials","service":"auth","result":{"recovered":False,"result":"credentials_valid_no_change"}},
   {"tool":"get_logs","service":"auth","result":["Auth token validation normal; no authentication failures observed"]},
   {"tool":"get_logs","service":"payment","result":["Request timeout while acquiring downstream persistence connection"]},
   {"tool":"get_metrics","service":"database","result":{"status":"degraded","connections":100,"max_connections":100}},
   {"tool":"recover_database_pool","service":None,"result":{"recovered":True,"result":"pool_recovered"}},
   {"tool":"verify_service","service":"payment","result":{"healthy":True,"status":"healthy"}},
   {"tool":"verify_service","service":"checkout","result":{"healthy":True,"status":"healthy"}}]},
  "regression":{"id":"RUN-6581a5318981","events":57,"verdict":{"status":"passed","memory_effect":"CORRECTLY_REJECTED","unnecessary_action_count":0},"replay":[
   {"tool":"get_metrics","service":"auth","result":{"status":"healthy","token_valid":True}},
   {"tool":"get_logs","service":"auth","result":["Auth token validation normal; no authentication failures observed"]},
   {"tool":"get_dependencies","service":"payment","result":["auth","database","queue"]},
   {"tool":"get_logs","service":"payment","result":["Request timeout while acquiring downstream persistence connection"]},
   {"tool":"recover_database_pool","service":None,"result":{"recovered":True,"result":"pool_recovered"}},
   {"tool":"verify_service","service":"payment","result":{"healthy":True,"status":"healthy"}},
   {"tool":"verify_service","service":"checkout","result":{"healthy":True,"status":"healthy"}}]}
 }
}
