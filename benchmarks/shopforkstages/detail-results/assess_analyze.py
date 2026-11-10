"""Assess retained SQL responses; missing optional total alone is not failure."""
from pathlib import Path
import argparse,json,math

def assess(raw,inputs):
 assessment=[]
 for row in raw['rows']:
  r=dict(repeat=row['repeat'],delay=row['delay'],wall_ms=row['wall_ms'],valid_json=False,finite_timings=False,plausible_total=False)
  try:
   def invalid(v): raise ValueError('nonfinite literal: '+v)
   obj=json.loads(row['raw'],parse_constant=invalid);r['valid_json']=True
   timings=[]
   def visit(o):
    if isinstance(o,dict):
     for k,v in o.items():
      if k.endswith('_time_ms'):timings.append((k,v))
      visit(v)
    elif isinstance(o,list):
     for v in o:visit(v)
   visit(obj)
   r['timing_fields']=timings;r['finite_timings']=bool(timings) and all(isinstance(v,(int,float)) and math.isfinite(v) and v>=0 for k,v in timings)
   r['total_ms']=obj['query_block'].get('r_total_time_ms')
   reported=max((v for k,v in timings if isinstance(v,(int,float)) and math.isfinite(v)),default=0)
   r['plausible_total']=r['finite_timings'] and (10 if row['delay'] else 0)<=reported<=row['wall_ms']*2+10
  except (ValueError,KeyError,TypeError) as e:r['assessment_error']=str(e)
  r['pass']=not row.get('error') and r['valid_json'] and r['finite_timings'] and r['plausible_total']
  assessment.append(r)
 result=dict(result='PASS' if all(r['pass'] for r in assessment) else 'BASELINE_TIMING_UNUSABLE',harness_source_commit=inputs['harness_source_commit'],binary_sha256=inputs['binary_sha256'],rows=assessment,subsequent_select='PASS',cleanup='PASS',timer_treatment_allowed=all(r['pass'] for r in assessment))
 return result

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
 p=Path(__file__).resolve().parent
 result=assess(json.loads((p/'analyze.json').read_text()),json.loads((p/'inputs.json').read_text()))
 text=json.dumps(result,indent=2)+'\n'
 if args.check: assert (p/'analyze-assessment.json').read_text()==text
 else: (p/'analyze-assessment.json').write_text(text)
 print(result['result'])
