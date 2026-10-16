"""Optional deterministic cost routing; local commands run before this module."""
from __future__ import annotations
import re
import providers

def choose(text,settings):
    manual=settings['provider']
    if manual=='local' or not settings.get('api_generation_enabled'):return {'provider':'local','reason':'local_mode','difficulty':'local'}
    if not settings.get('routing_enabled'):return {'provider':manual,'model':settings['chat_models'][manual],'reason':'manual_selection','difficulty':'manual'}
    complex_input=len(text)>350 or bool(re.search(r'推导|证明|电路|微电子|半导体|debug|代码|架构|论文|多步|分析.{0,12}(?:原因|方案|差异)|比较.{0,20}(?:方案|原理)|法律|医疗|投资',text,re.I))
    provider=settings.get('routing_complex_provider','gemini') if complex_input else settings.get('routing_cheap_provider','deepseek')
    if provider=='local':return {'provider':'local','reason':'optional_local_route','difficulty':'complex' if complex_input else 'simple'}
    model=settings['chat_models'][provider]
    # Unknown pricing is never picked automatically as the cheap path.
    if not complex_input and providers.model_rates(provider,model) is None:
        return {'provider':manual,'model':settings['chat_models'][manual],'reason':'unknown_cheap_price_use_manual','difficulty':'simple'}
    if not complex_input:
        manual_model=settings['chat_models'][manual];manual_rates=providers.model_rates(manual,manual_model)
        candidate_rates=providers.model_rates(provider,model)
        # Compare the same illustrative input/output mix; this is a routing
        # estimate, never a supplier bill or a promise about token usage.
        if manual_rates and candidate_rates and manual_rates[0]+manual_rates[1]/4<candidate_rates[0]+candidate_rates[1]/4:
            return {'provider':manual,'model':manual_model,'reason':'manual_model_lower_estimate','difficulty':'simple'}
    return {'provider':provider,'model':model,'reason':'complex_input' if complex_input else 'simple_input','difficulty':'complex' if complex_input else 'simple'}
