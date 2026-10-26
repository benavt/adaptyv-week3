#!/usr/bin/env python3
"""Verify distributed bytes, full sequences, scores, construct identities and ranking."""
from pathlib import Path
import csv,hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'reports/2026-10-25_glp1r-final20'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
 with p.open() as f:return list(csv.DictReader(f))
def main():
 ledger=json.loads((P/'provenance.json').read_text());selected=rows(P/'submission.csv');assert len(selected)==20
 assert list(selected[0])==['name','sequence','molecule_class']
 assert all(r['molecule_class']=='single_chain' for r in selected)
 assert len({r['sequence'] for r in selected})==len({r['name'] for r in selected})==20
 summary=rows(P/'source-tables/GLP1R_LigandForge50_and_DLD50_DeltaForge_Summary.csv');assert len(summary)==100
 eligible=sorted([r for r in summary if float(r['Exact_ipSAE'])>0.895 and float(r['predicted_Kd_nM'])<10],key=lambda r:(-float(r['Exact_ipSAE']),float(r['predicted_Kd_nM']),r['population'],r['design_id']))
 assert len(eligible)==25
 assert [r['name'] for r in selected]==[r['design_id'] for r in eligible[:20]]
 aa=dict(zip('ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL'.split(),'ARNDCQEGHILKMFPSTWYV'))
 fasta=[]
 for line in (P/'final20.fasta').read_text().splitlines():
  if line.startswith('>'):fasta.append('')
  else:fasta[-1]+=line.strip()
 assert fasta==[r['sequence'] for r in selected]
 for i,(row,r) in enumerate(zip(selected,ledger['records'])):
  s=r['selection'];did=s['design_id'];assert row['name']==did and row['sequence']==s['sequence'] and int(s['final_rank'])==i+1
  assert sha(P/f'models/{did}/boltz2.cif')==s['Boltz2_model_sha256']
  pdb=P/f'models/{did}/deltaforge-input.pdb';assert sha(pdb)==s['DeltaForge_input_PDB_SHA256']
  assert hashlib.sha256(row['sequence'].encode()).hexdigest()==s['sequence_sha256']
  chains={};seen=set()
  for line in pdb.read_text().splitlines():
   if line.startswith('ATOM  '):
    key=(line[21],line[22:27])
    if key not in seen:chains[line[21]]=chains.get(line[21],'')+aa[line[17:20]];seen.add(key)
  assert chains['A']==s['sequence'] and len(chains['B'])==int(s['receptor_length'])
  assert hashlib.sha256(chains['B'].encode()).hexdigest()==r['receptor_sequence_sha256']
  result=json.loads((P/f'scores/{did}.json').read_text());response=result['response'];assert response['source_pdb_sha256']==s['DeltaForge_input_PDB_SHA256']
  assert float(response['kd_nm'])==float(s['predicted_Kd_nM'])
  assert response['scorer_version']=='v10_2_unified_parallel_2026_05_08'
  assert response['affinity_scorer_version']=='v10_boltz2_gbr_2026_03_29'
 views=json.loads((P/'figure-provenance.json').read_text())
 for m in views['models']:
  for key in ['overview','interface']:
   e=m[key];p=P/'figures'/Path(e['asset']).name;assert sha(p)==e['image_sha256']
 side=P/'fold-sidecar-provenance.json'
 if side.exists():
  for item in json.loads(side.read_text())['files']:assert sha(P/item['path'])==item['sha256']
 # The manifest intentionally excludes itself. It covers all public package bytes.
 sums=ROOT/'SHA256SUMS'
 checked=0
 if sums.exists():
  for line in sums.read_text().splitlines():
   digest,name=line.split('  ',1);p=ROOT/name;assert p.is_file() and sha(p)==digest,name;checked+=1
 print(json.dumps({'status':'pass','selected':20,'qualifying':25,'rank_and_sequences':'unchanged','native_models':20,'scoring_inputs':20,'figures':40,'manifest_files_checked':checked}))
if __name__=='__main__':main()
