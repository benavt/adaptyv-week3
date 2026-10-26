# Human GLP1R final20

Twenty selected exact sequences ranked by highest Boltz2 Exact ipSAE after the strict ipSAE>0.895 and predicted Kd<10nM filter. The selection contains6 original LigandForge and14 D-L-D molecules. Predicted affinity and interface confidence do not establish measured binding or receptor activation.

- [Final writeup](GLP1R_Week3_Final20_Final_Writeup.pdf) and [editable manuscript](manuscript.md)
- [Ranked submission CSV](submission.csv), all rows single_chain
- [Sequences](candidate-sequences.csv) and [FASTA](final20.fasta)
- [40-slide metric and structure companion](GLP1R_Final20_Metrics_and_Structures.pptx)
- [Full-precision selected metrics](final20-metrics.csv)
- [Scientific provenance](provenance.json), [figure provenance](figure-provenance.json), [publication file manifest](file-manifest.json)
- models/: exact scientific native CIFs, exact DeltaForge input PDBs and selected native fusion-generator models
- parents/: available parent-generator models and separately serialized standalone Exact display PDBs
- scores/: saved score-response publication derivatives
- source-tables/: complete scored top50 tables and100-candidate combined summary
- methods/: effective source settings and native software/weight/scorer identities

The original LigandForge models use409-aa receptor references and the D-L-D models440 aa. Native and scoring coordinates remain unchanged. Figure images use the agreed molecule-identity colors and retain independent full/interface zooms. Original LigandForge generator coordinates are unavailable. Publication derivatives normalize private infrastructure paths; original source hashes remain recorded. Remaining full-population artifacts remain in private retained scientific storage.

All68 selected native confidence/PAE/PDE/pLDDT sidecars were collected read-only through Fleet and verified against the historical source hashes. Their file identities are in fold-sidecar-provenance.json.
