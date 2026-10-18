# Jannik Sinner reference analysis

219 serves listed in dataset metadata: 152 first serves, 67 second serves, seven matches. All 219 filenames have IDs in the cached public Drive listing. All 219 poses have now been downloaded and analyzed (17,084 frames). All source checksums verified; three analysis tests passed. The animation was generated and its preview inspected.

Run `sh run.sh` from this directory with network access. Downloads resume by skipping existing pose files. The script verifies pose shape, finite values and metadata frame counts; computes eight angles; estimates phases; tests full-cohort statistics and alignment; then renders `sinner-219-serves.gif` and `preview.png`. The full run refuses incomplete cohorts. Results and source checksums go in `results/`.

The method is the same as ../reference/README.md: provisional H36M joint mapping, included 3D segment angles, estimated knee minimum and right-wrist height events aligned to 40% and 80% of a common grid. These are body-only proxies, not observed contact or racket events. Bands show pointwise 10th–90th percentiles, not confidence intervals. First and second serve distributions are computed separately in distribution.json. No confidence scores or validated camera/coordinate mapping are available; this is descriptive research, not a validated coaching target. No canonical DMS mapping is asserted.

Source: https://github.com/jasnwag/tennis_serve_dataset at commit 7889457cc9b50b0c2a9fdcc81d786bcdb6b8652c. Metadata and pose exports: CC BY 4.0, see DATA_LICENSE. Analysis adapted from the local Djokovic reference pipeline.

## Quality results

All 219 serves contain at least one adjacent-frame angle jump greater than 40 degrees. 73 have smoothing-sensitive phase estimates (including the diagnostic elbow event), 10 have broad wrist-height peaks, and two hit the wrist search boundary. All serves remain included. Variation includes tracking and alignment uncertainty.
