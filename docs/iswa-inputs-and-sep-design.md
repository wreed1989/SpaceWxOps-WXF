# iSWA inputs and a WXF event-triggered proton model

Reviewed September 19, 2026. This is an implementation and validation design,
not a newly trained forecast. The radiation UI changes are implemented; the
candidate inputs below have not been added to production model weights.

## Highest-value additions

The useful distinction is between observations that add information, provider
forecasts used as benchmarks, and alternate delivery of observations already
ingested. A mirror is not an independent measurement or an extra ensemble member.
iSWA exposes numeric time series through [HAPI and its documented API](https://ccmc.gsfc.nasa.gov/tools/ISWA/).

The entries below were checked against live API metadata and, for the four
current observational feeds, actual recent numeric rows. Times are UTC on
September 19 unless another date is shown. These are availability checks, not
model-skill results.

| Priority / product | Evidence checked | Proposed WXF use and qualification |
| --- | --- | --- |
| **1. ACE EPAM electron and ion channels** | [HAPI `ace_epam_P5M`](https://iswa.ccmc.gsfc.nasa.gov/hapi/info?id=ace_epam_P5M): five-minute values present through 23:15 | Add electron rise, slope and background features to SEP updates; evaluate low-energy ion history as a seed-population proxy. ACE EPAM is already displayed in WXF, so the new work is feature engineering and validation. Its interplanetary electrons are different from GEO >2 MeV electrons used for internal-charging fluence. |
| **2. GOES magnetic-field vectors** | [HAPI `goesp_mag_p1m`](https://iswa.ccmc.gsfc.nasa.gov/hapi/info?id=goesp_mag_p1m): actual GOES-19 row through 23:21 | Test field-change and compression signatures as electron-dropout discriminators, together with upstream pressure and storm phase. Retain spacecraft identity and local time; a field change at one GEO location is not a measurement of the entire belt. |
| **3. Dst history and storm phase** | [HAPI `dst_quicklook`](https://iswa.ccmc.gsfc.nasa.gov/hapi/info?id=dst_quicklook): hourly value through 22:00 | Test lagged Dst, its change and recovery duration alongside existing wind/Bz features. Dst is already displayed in the desk. Use quicklook data as issued in prospective operation, and flag later revisions when using definitive data in retrospective work. |
| **4. SEPSTER numeric forecasts and connectivity** | [iSWA data ID 1241](https://iswa.ccmc.gsfc.nasa.gov/api/recent?dataID=1241&n=1): issued 21:31:12; sample window ends September 20 at 21:09 | A current, event-triggered comparator with CME identity, Parker-spiral connectivity and integral >10/>50 MeV peak predictions. Its sample >50 MeV all-clear criterion is **1 PFU**, not the office's 10 PFU trigger. Preserve the prediction's threshold and quantity; do not reinterpret its all-clear flag. |
| **5. GOES particle history and cross-satellite quality** | [HAPI `goesp_part_flux_P5M`](https://iswa.ccmc.gsfc.nasa.gov/hapi/info?id=goesp_part_flux_P5M): actual particles through 23:15; separate electron/proton satellite IDs | Useful archive/mirror and consistency checks for feeds already ingested from NOAA. The inspected row has fill values for E_8 and E4_0, while E2_0 is populated. Catalog channel names alone do not prove usable coverage. Never turn fills into zero or infer an electron spectrum from absent channels. |

The suggested features are physical hypotheses to test. Promotion should require
an improvement over the existing model on untouched time periods, with the same
forecast lead time, availability constraints and missing-data policy.

## Entries that should not be treated as live inputs

- [SWMF2023_RT_GMlog_P1M](https://iswa.ccmc.gsfc.nasa.gov/hapi/info?id=SWMF2023_RT_GMlog_P1M)
  reports its last available time as **December 16, 2025**. This specific stream
  is unsuitable for live September 2026 alerts, despite “RT” in its name. This
  finding does not imply every SWMF stream has stopped.
- [RBSP_A_ECTHOPE_e_FLUX_P1M](https://iswa.ccmc.gsfc.nasa.gov/hapi/info?id=RBSP_A_ECTHOPE_e_FLUX_P1M)
  ends **December 23, 2016** in this catalog. It can inform historical physical
  studies; it is not a present-day radiation-belt feed.
- [MAG4 SHARP FE, ID 1380](https://iswa.ccmc.gsfc.nasa.gov/api/recent?dataID=1380&n=1)
  returns a June 3, 2026 issue with a June 4 validity end. Do not present this
  inspected variant as current guidance. Other MAG4 variants need their own checks.
- [iPATH, ID 2577](https://iswa.ccmc.gsfc.nasa.gov/api/recent?dataID=2577&n=1)
  returns a September 15 issue for a September 14 CME; its window ends September
  17 and its submission says **nowcast**. It is useful event evidence, not an
  active forecast for today. Event-driven products can legitimately have no
  current event, so an older event does not alone establish a failed service.

These checks are saved in `docs/iswa-availability-2026-09-19.json`. UMASEP-10/50,
REleASE, DONKI CME/IPS, HUXt, ENLIL and the CME Scoreboard are already connected.
The priority is to exploit their issue-time information correctly, not duplicate
them under another provider label. No radiation forecasting method is introduced.

## The SWPC tool and what the supplied procedure adds

The documented SWPC **PROTONS / Proton Prediction Model** uses peak and integrated
soft X-rays and Type II/IV bursts; flare position informs timing. Prior-region
flare fluence also enters the published peak-flux method. The public description
supports >10 MeV probability, peak intensity and peak time.
[SWPC presentation](https://www.swpc.noaa.gov/sites/default/files/images/u59/05%20Hazel%20Bain%20Official.pdf),
[model review hosted by NOAA](https://repository.library.noaa.gov/view/noaa/52048/noaa_52048_DS1.pdf).

The supplied procedure describes a broader interface: integral/differential
protons, onset, PCA, SST dose and sudden commencement / subsequent Ap. That is
a useful requirements list, but it does not disclose the algorithms for every
output. Public documentation distinguishes SWPC PPM from **AFRL PPS**, whose
described outputs include >5/>10/>50 MeV profiles and onset/peak/end times.
We should not call a new WXF method an exact reproduction of either system.
[CCMC model comparison](https://ccmc.gsfc.nasa.gov/scoreboards/sep/).

One important correction to the procedure's interpretation: Balch's historical
**20–30%** result is a useful *decision-threshold range* for maximizing Heidke
skill in that study. It does not mean only forecasts with probabilities in that
band are trustworthy. Its approximately **55% FAR** is false alarms divided by
all issued positive forecasts, not the fraction of all quiet periods that false
alarm. These are historical evaluation results, not measured 2026 performance or
WXF skill. The study also notes overlap between training and verification data.
[Balch 2008](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2007SW000337).

## Proposed WXF model

Build an event record for each flare, update it as new observations arrive, and
keep every issued forecast version. A practical first version would have:

1. **Inputs:** UTC flare peak date/time, peak class, measured heliographic
   position with uncertainty, region identity/history, and integrated 1–8 Å
   X-ray flux in J/m². Store start/peak/end definitions and calibration version.
   Do not replace the actual UTC peak date with the computer's current date.
2. **Additional discriminators:** Type II/III/IV reports, observed CME geometry
   and speed, solar-wind-dependent magnetic connection angle, background
   particles, and EPAM electron rise. Optical class is optional. Record source,
   observation time, arrival time and quality for every input; retain “unknown”
   separately from a confirmed absence.
3. **Targets:** probabilities of crossing the office's >10 MeV 10 PFU and
   40 PFU criteria, plus >50 MeV 10 PFU; conditional onset windows, peak-flux
   distributions and timing. Select and record a verification horizon explicitly
   rather than leaving “a proton enhancement” undefined. Implement the exact
   equality conventions as configured office criteria, separate from NOAA S levels.
4. **Method:** begin with regularized probabilistic models and a calibrated
   event-timing model, then compare more flexible models. Estimate uncertainty
   from held-out residuals or event resampling, not arbitrary percentage growth.
   Solar-only guidance should be distinguishable from updates already informed
   by particles approaching or exceeding the event threshold.
5. **Validation:** chronological held-out years/solar-cycle segments, grouped by
   eruption sequence/active region; include all eligible non-SEP flares. Check
   probability reliability, Brier skill versus climatology, precision/POD/FAR,
   warning lead time, onset errors and interval coverage. Report sample sizes,
   particularly for rarer >50 MeV cases. Ablate each added discriminator to show
   whether it improves skill at the same lead time. Do not report training-fit
   statistics as independent verification.

These are design recommendations, not fitted coefficients. For early issues,
integrated flux is only the integral available *so far*; using the completed
flare integral before the flare ends would leak future information. SWPC's
event end is defined relative to the preflare background and peak, and XRS
calibration differs across GOES generations. A historical reconstruction must
respect both. [SWPC X-ray product definitions](https://www.swpc.noaa.gov/products/goes-x-ray-flux).

A Type II burst is evidence of a shock, not proof that the shock will hit Earth.
Type IV emission traces energetic electrons in coronal magnetic structures;
it is not itself a measurement of CME bulk mass or >50 MeV proton production.
[Radio-burst physics](https://www.nrao.edu/astrores/gbsrbs/Pubs/AJP_07.pdf).
Use connection angle relative to an estimated field-line footpoint, not a rule
that probability rises indefinitely toward the western limb.

## Keep the output physics separate

| Requested output | Appropriate branch |
| --- | --- |
| Integral >10 / >50 MeV protons | Calibrated SEP occurrence, intensity and timing model. Integral flux is energy-integrated intensity, not a total count. Differential intensity is per energy interval; its units include inverse energy. |
| Polar-cap absorption in dB | A separate absorption calculation with a stated radio frequency/path convention, proton spectrum, illumination and geomagnetic access. Office “Near PCA / PCA” PFU triggers are decision labels, not direct measured absorption in dB. [NOAA D-RAP physics](https://www.swpc.noaa.gov/content/global-d-region-absorption-prediction-documentation). |
| 20 km effective dose | Present NAIRAS nowcast in Alerts. Future transport/dose forecasting remains deferred. 3 mrem/h = 0.03 mSv/h is a unit conversion, not proof that legacy SST dose is the same physical quantity. [NAIRAS definitions](https://ccmc.gsfc.nasa.gov/models/NAIRAS~4/). |
| Shock arrival / sudden commencement | Use CME/HSS propagation and observed DONKI IPS associations to build a separately verified shock-impact model. HUXt or ENLIL bulk-plasma arrival time is not energetic-proton onset. |
| Post-impact geomagnetic response / aurora | Requires magnetic coupling and its uncertainty. Shock arrival does not determine future Bz, Ap or visible aurora. Keep observed 3-hour ap distinct from daily Ap. [NOAA OVATION](https://www.swpc.noaa.gov/products/aurora-30-minute-forecast) uses upstream solar wind/IMF for short-lead auroral guidance. |

The supplied rise-time label should also be made explicit: the PROTONS review
defines flare X-ray maximum to proton maximum, whereas “proton rise time” can
also mean proton onset to proton peak. Store both timestamps rather than
silently treating these intervals as interchangeable.

For comparison against the SEP Scoreboard, preserve each submission's energy
channel, threshold, issue time, mode and validity interval. A benchmark is not an
independent input when it uses the same GOES data. CCMC also asks users to notify
the center and submitting model teams before a validation study using that
database. This review has only inspected availability and documentation; no such
study or external communication has been performed.

The first build should therefore be a **WXF experimental SEP event model** with
an auditable input record and held-out verification. PCA, shock/geomagnetic
response and eventual radiation forecasts can share the event record while
retaining their own targets and validation.
