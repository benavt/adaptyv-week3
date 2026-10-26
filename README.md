# Adaptive Week3 human GLP1R designs

This repository contains the final computational writeup and inspectable scientific evidence for20 selected human GLP1R candidate sequences. The candidates comprise6 original LigandForge designs and14 D-L-D fusions. Selection first requires Boltz2 Exact ipSAE>0.895 and DeltaForge predicted Kd<10nM within two scored top50 populations, then retains the highest20 Exact ipSAE values.

[Open the final report and evidence package](reports/2026-10-25_glp1r-final20/README.md).

[Final PDF](reports/2026-10-25_glp1r-final20/GLP1R_Week3_Final20_Final_Writeup.pdf) · [Ranked submission CSV](reports/2026-10-25_glp1r-final20/submission.csv) · [Scientific provenance](reports/2026-10-25_glp1r-final20/provenance.json).

Native selected models, affinity inputs, saved scores, source rankings, generation/parent lineage, method settings, figure provenance and portable verification/build scripts accompany the report. No model training or weights are distributed. Infrastructure bindings, credentials, account receipts and bulk unselected populations remain outside this repository.

All reported affinities are computational predictions. The409-aa and440-aa receptor construct distinction is preserved. This report does not establish binding or receptor activation, and publishing the repository does not submit candidates to the competition.

The original scientific release is preserved as week3-final20-2026-10-25. The main branch contains the latest reader edition, with plain-language provenance and no hashes in the report.

## Verification

Run `python3 scripts/verify_release.py` to verify the distributed hashes, candidate identities and ranking. Rebuilding the PDF requires Python with reportlab and Pillow plus DejaVu Sans/Mono fonts; see `scripts/build_writeup.py --help`.
