"""Image-only host reviewer, separate from generator history/code, with PNG caching."""
import base64, hashlib, json, os, re
from pathlib import Path
import gemini_client, openai_client

ROOT=Path(__file__).resolve().parents[2]
PROMPT=Path(__file__).with_name('framebuffer_judge_prompt.txt')
CACHE=ROOT/'simulator/build/vision-cache'
RUBRIC=['No widget or text is cut off at the edges of the display',
        'No text overlaps other text or an unrelated control',
        'All text is readable with clear contrast against its actual background',
        'Whole groups and grids fit inside their visible containers, with no clipped outer cells or unintended scrolling',
        'Repeated grid cells of the same role have aligned rows and columns, consistent sizes and gaps, and the complete requested count',
        'Placement, grouping and scrolling suit the requested task: compact single-board games use a balanced centred composition unless positioned otherwise; lists, forms and explicitly aligned layouts are not forced to centre']

def initial_criteria(criteria,theme):
    # Both palettes deliberately keep the same text/state. Root colour-only
    # expectations must refer to the build under review, not a stale spec colour.
    result=[]
    for criterion in criteria:
        if re.search(r'switch',criterion,re.I) and re.search(r'\bDark\b',criterion) and re.search(r'\bLight\b',criterion) and re.search(r'\b(?:on|off|left|right)\b',criterion,re.I):
            result.append('The theme switch knob matches its visible adjacent label: right/on when the label reads Light, left/off when the label reads Dark. Judge the label, not the background colour.')
            continue
        root_colour=(re.search(r'background',criterion,re.I) and re.search(r'\b(?:dark|black|white|light)\b',criterion,re.I)
                     and not re.search(r'text|readab|contrast|button|label|widget|switch|#[0-9a-f]',criterion,re.I))
        result.append(f'The initial display background uses the {theme} compile-time test palette.' if root_colour else criterion)
    return result

def settings():
    provider=os.environ.get('SIM_JUDGE_PROVIDER') or os.environ.get('GENERATOR_PROVIDER','gemini')
    if provider=='openai':
        return provider,os.environ.get('OPENAI_JUDGE_MODEL') or os.environ.get('OPENAI_MODEL'),openai_client.generate,{
            'key_var':'OPENAI_JUDGE_API_KEY' if os.environ.get('OPENAI_JUDGE_API_KEY') else 'OPENAI_API_KEY'}
    if provider=='gemini':
        return provider,os.environ.get('GEMINI_JUDGE_MODEL') or os.environ.get('GEMINI_MODEL'),gemini_client.generate,{
            'key_var':'GEMINI_JUDGE_API_KEY' if os.environ.get('GEMINI_JUDGE_API_KEY') else 'GEMINI_API_KEY','fallback_model':''}
    raise RuntimeError('SIM_JUDGE_PROVIDER must be openai or gemini')

def judge_captures(test_name,intent,captures,generate=None,cache_dir=None):
    provider,model,client,options=settings();client=generate or client
    prompt=PROMPT.read_text(encoding='utf-8')
    parts=[];identity={'prompt':prompt,'provider':provider,'model':model,'intent':intent,'captures':[]}
    for cap in captures:
        png=Path(cap['photo']).read_bytes()
        if not png.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Judge requires framebuffer PNG captures')
        info={'label':cap['label'],'after':cap['after'],'criteria':cap['expect_visual']}
        identity['captures'].append(dict(info,png_sha256=hashlib.sha256(png).hexdigest()))
        parts.append({'type':'text','text':json.dumps(info,ensure_ascii=False)})
        if provider=='openai':parts.append({'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(png).decode('ascii'),'detail':'high'}})
        else:
            parts[-1]={'text':parts[-1]['text']}
            parts.append({'inline_data':{'mime_type':'image/png','data':base64.b64encode(png).decode('ascii')}})
    key=hashlib.sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    cache=Path(cache_dir) if cache_dir is not None else CACHE
    path=cache/(key+'.json');data=None;cached=False
    if path.exists():
        try:data=json.loads(path.read_text(encoding='utf-8'));_validate(data,captures);cached=True
        except (ValueError,TypeError,KeyError):data=None
    if data is None:
        intro={'type':'text','text':'Review these framebuffer captures. Interface intent: '+intent} if provider=='openai' else {'text':'Review these framebuffer captures. Interface intent: '+intent}
        messages=[('user',[intro]+parts)]
        for attempt in range(2):
            reply=client(prompt,messages,model=model,json_output=True,**options)
            try:
                text=reply.strip()
                if text.startswith('```'):text=text.split('\n',1)[1].rsplit('```',1)[0]
                data=json.loads(text);_validate(data,captures);break
            except (ValueError,TypeError,KeyError) as exc:
                data=None
                messages.append(('user','Return complete JSON with every label and every criterion in their supplied order. '+str(exc)))
        if data is None:raise gemini_client.GeminiError('Image judge returned incomplete or malformed verdicts.','The image reviewer could not complete its checks. Your previous interface is preserved; please retry.')
        cache.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(temporary,path)
    failures=[];verdict={'test':test_name,'provider':provider,'model':model,'cached':cached,'cache_key':key,'captures':[]}
    for cap,answer in zip(captures,data['captures']):
        verdict['captures'].append(dict(answer,photo=str(cap['photo'])))
        for criterion in answer['criteria']:
            if not criterion['pass']:failures.append({'kind':'visual','test':cap.get('test',test_name),'label':cap['label'],
                'expected':criterion['criterion'],'actual':criterion['reason'],'photo':str(cap['photo'])})
    return failures,verdict

def _validate(data,captures):
    answers=data.get('captures') if isinstance(data,dict) else None
    if not isinstance(answers,list) or len(answers)!=len(captures):raise ValueError('Wrong number of captures')
    for cap,answer in zip(captures,answers):
        if not isinstance(answer,dict) or answer.get('label')!=cap['label']:raise ValueError('Missing or reordered capture label')
        criteria=answer.get('criteria')
        if not isinstance(criteria,list) or len(criteria)!=len(cap['expect_visual']):raise ValueError('Wrong number of criteria')
        for wanted,actual in zip(cap['expect_visual'],criteria):
            if not isinstance(actual,dict) or actual.get('criterion')!=wanted or type(actual.get('pass')) is not bool or not isinstance(actual.get('reason'),str) or not actual['reason'].strip():raise ValueError('Incomplete criterion result')
