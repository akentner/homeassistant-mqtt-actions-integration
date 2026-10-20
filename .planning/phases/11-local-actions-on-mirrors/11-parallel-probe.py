import asyncio
import json
import tempfile
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from custom_components.mqtt_actions.trust import guard_actions
from homeassistant.core import HomeAssistant, Context, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.script import Script, async_validate_actions_config
from homeassistant.helpers.trace import trace_get
from homeassistant.helpers import config_validation as cv

async def main():
    hass = HomeAssistant(tempfile.mkdtemp(prefix='phase11-ha-'))
    events = []
    async def fail(call):
        events.append('owner_fail')
        raise HomeAssistantError('OWNER_FAILURE')
    async def fail_local(call):
        events.append('local_fail')
        raise HomeAssistantError('LOCAL_FAILURE')
    async def finish(call):
        await asyncio.sleep(.02)
        events.append('local_finished')
    async def after(call):
        events.append('after')
    async def response(call):
        return {'answer': call.data['answer']}
    async def denied(call):
        events.append('local_denied_service_ran')
    for name, handler in [('fail',fail), ('fail_local', fail_local), ('finish',finish), ('after',after)]:
        hass.services.async_register('probe', name, handler)
    hass.services.async_register('probe', 'response', response, supports_response=SupportsResponse.ONLY)
    hass.services.async_register('mqtt', 'publish', denied)
    cases = {
      'owner_failure': [[{'action':'probe.fail'}], [{'action':'probe.finish'}]],
      'both_fail': [[{'action':'probe.fail'}], [{'action':'probe.fail_local'}]],
      'stop': [[{'stop':'normal stop'}], [{'action':'probe.finish'}]],
      'error_stop': [[{'stop':'error stop', 'error':True}], [{'action':'probe.finish'}]],
      'continue_homeassistant_error': [[{'action':'probe.fail','continue_on_error':True}, {'action':'probe.after'}], [{'action':'probe.finish'}]],
      'stop_response': [[{'variables':{'answer':{'branch':'owner'}}}, {'stop':'response','response_variable':'answer'}], [{'action':'probe.finish'}]],
      'distinct_response_variables': [[{'action':'probe.response','data':{'answer':'owner'},'response_variable':'owner_reply'}], [{'action':'probe.response','data':{'answer':'local'},'response_variable':'local_reply'}]],
      'same_response_variable': [[{'action':'probe.response','data':{'answer':'owner'},'response_variable':'reply'}], [{'action':'probe.response','data':{'answer':'local'},'response_variable':'reply'}]],
      'owner_stop_local_failure': [[{'stop':'normal stop'}], [{'action':'probe.fail_local'}]],
      'owner_guard_local_unrestricted': [[{'action':"{{ 'mqtt.publish' }}",'continue_on_error':True}], [{'action':"{{ 'mqtt.publish' }}"}]],
    }
    for name, branches in cases.items():
        events.clear()
        trace = trace_get()
        sequence = await async_validate_actions_config(hass, cv.SCRIPT_SCHEMA([{'parallel':[{'sequence':s} for s in branches]}, {'action':'probe.after'}]))
        if name == 'owner_guard_local_unrestricted':
            sequence[0]['parallel'][0]['sequence'] = guard_actions(sequence[0]['parallel'][0]['sequence'])
        script = Script(hass, sequence, name, 'probe', script_mode='queued')
        result = None
        caught = None
        try:
            result = await script.async_run({}, Context())
        except Exception as err:
            caught = type(err).__name__ + ':' + str(err)
        errors = {p:[e.as_dict().get('error') for e in es if e.as_dict().get('error')] for p,es in trace.items()}
        print(json.dumps({'case':name,'events':events.copy(),'exception':caught,'response':getattr(result,'service_response',None),'variables':{k:v for k,v in result.variables.items() if k != 'context'} if result else None,'errors':{p:e for p,e in errors.items() if e}}, default=str))
        await script.async_unload()
    await hass.async_stop(force=True)

asyncio.run(main())
