/* Generated automatically by the SpaceWxOps WXF workflow. */
window.FLARE_GUIDANCE_PAYLOAD = {
  "schema_version": "5.0",
  "model_version": "sharp-mag-20260903-xstruct-history-v3",
  "script_version": "2.0.0",
  "operational": false,
  "probability_scale": "percent",
  "issued": "2026-11-07T21:00:00Z",
  "valid_start": "2026-11-08T00:00:00Z",
  "valid_end": "2026-11-09T00:00:00Z",
  "quality": {
    "level": "research",
    "message": "Daily WXF inference from a saved calibrated M1+ model and an independently calibrated magnetic/history X1+ model. Research/shadow guidance unless explicitly validated and marked operational."
  },
  "input": {
    "series": "hmi.sharp_cea_720s_nrt",
    "target_time": "2026-11-07T18:00:00Z",
    "latest_record": "2026-11-07T18:00:00Z",
    "oldest_retained_record": "2026-11-07T18:00:00Z",
    "raw_records": 1992,
    "retained_regions": 6,
    "mapping": {
      "skipped_multi_region_harps": 0,
      "skipped_unmapped_harps": 11,
      "expanded_rows": 8
    },
    "quality": {
      "input": 8,
      "rejected_longitude": 2,
      "after_longitude": 6,
      "quality_missing": 0,
      "quality_top_values": {
        "0x00010400": 6
      },
      "rejected_quality": 0,
      "after_quality": 6,
      "rejected_harp_merge": 0,
      "after_harp_merge": 6,
      "rejected_observer_velocity": 0,
      "after_observer_velocity": 6,
      "rejected_missing_mapping": 0,
      "after_mapping": 6,
      "min_finite_parameters": 12,
      "rejected_parameter_completeness": 0,
      "after_parameter_completeness": 6,
      "retained": 6
    },
    "flare_history": {
      "available": true,
      "source": "https://services.swpc.noaa.gov/json/edited_events.json",
      "events": 17,
      "m1_plus_events": 17,
      "x1_plus_events": 0
    },
    "swpc_full_disk": {
      "available": true,
      "source": "https://services.swpc.noaa.gov/text/3-day-solar-geomag-predictions.txt",
      "issued": "2026-11-07T22:00:00+00:00",
      "valid_date": "2026-11-08"
    }
  },
  "wxf_full_disk": {
    "method": "union_of_unique_region_components",
    "formula": "1 - product(1 - regional probability)",
    "components": 6,
    "numbered_regions": 7,
    "sharp_regions": 6,
    "shared_harp_region_values": 2,
    "fallback_regions": 1,
    "unnumbered_or_farside_residual": false,
    "note": "Coverage aggregate, not a separately trained full-disk classifier. Shared HARP probabilities are included once. The product formula assumes independent components and is not a validated full-disk calibration."
  },
  "wxf_region_components": [
    {
      "component_id": "AR14567-fallback",
      "m1": 2.0,
      "x1": 0.0
    },
    {
      "component_id": "HARP14146",
      "m1": 0.4255405368317442,
      "x1": 0.06321804639143333
    },
    {
      "component_id": "HARP14155",
      "m1": 2.2092996842761554,
      "x1": 0.19268783063954076
    },
    {
      "component_id": "HARP14160",
      "m1": 61.48759572178869,
      "x1": 0.5306831210800181
    },
    {
      "component_id": "HARP14165",
      "m1": 0.43531622802389075,
      "x1": 0.04892694429332099
    },
    {
      "component_id": "HARP14169",
      "m1": 0.2192610451832148,
      "x1": 0.03520153886364335
    }
  ],
  "regions": [
    {
      "id": "full-disk",
      "label": "Full Disk",
      "quality": {
        "level": "research",
        "message": "Visible-disk WXF coverage aggregate. Accepted SHARP components and explicit morphology/climatology fallbacks are combined once per HARP/region."
      },
      "drivers": [
        "7 numbered active regions represented",
        "6 SHARP region values; 1 fallbacks",
        "Regional probabilities combined as 1 - product(1 - p_i)",
        "Shared HARPs counted once in the full-disk aggregate",
        "No unnumbered or farside residual term"
      ],
      "members": {
        "sharpmag": {
          "m1": 63.5,
          "x1": 0.9,
          "source": "WXF sharp-mag-20260903-xstruct-history-v3 regional combination",
          "quality": "research",
          "method": "regional_union_with_explicit_fallbacks"
        },
        "swpc": {
          "m1": 60.0,
          "x1": 20.0,
          "source": "NOAA/SWPC 3-day whole-disk flare forecast",
          "quality": "official-operational",
          "method": "official_swpc",
          "issued": "2026-11-07T22:00:00+00:00",
          "valid_start": "2026-11-08T00:00:00+00:00",
          "valid_end": "2026-11-09T00:00:00+00:00"
        },
        "mcstat": {
          "m1": 24.0,
          "x1": 2.0,
          "source": "SolarMonitor MCSTAT dominant-region proxy (maximum of 6 regional forecasts)",
          "quality": "published-comparison"
        },
        "mcevol": {
          "m1": 4.0,
          "x1": 0.0,
          "source": "SolarMonitor MCEVOL dominant-region proxy (maximum of 6 regional forecasts)",
          "quality": "published-comparison"
        },
        "sidc": {
          "m1": 0.0,
          "x1": 0.0,
          "source": "SIDC 24-hour Global Flare Forecast",
          "quality": "published-comparison",
          "issued": "2026-11-07T12:43:44Z",
          "valid_start": "2026-11-07T12:43:44Z",
          "valid_end": "2026-11-08T12:43:44Z",
          "note": "Human-operator-moderated global forecast published by SIDC."
        },
        "ccmc_amos": {
          "m1": null,
          "x1": 10.09,
          "source": "NASA/CCMC Flare Scoreboard · CCMC AMOS",
          "quality": "published-comparison",
          "issued": "2026-11-08T00:30:00Z",
          "valid_start": "2026-11-08T00:00:00Z",
          "valid_end": "2026-11-09T00:00:00Z",
          "note": "Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI feed using the /data parameter schema.",
          "dataset_id": "AMOS_v1_FULLDISK"
        },
        "ccmc_assa24": {
          "m1": null,
          "x1": 3.96,
          "source": "NASA/CCMC Flare Scoreboard · CCMC ASSA 24H",
          "quality": "published-comparison",
          "issued": "2026-11-08T00:00:00Z",
          "valid_start": "2026-11-08T00:00:00Z",
          "valid_end": "2026-11-09T00:00:00Z",
          "note": "Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI feed using the /data parameter schema.",
          "dataset_id": "ASSA_24H_1_FULLDISK"
        },
        "ccmc_assa": {
          "m1": null,
          "x1": 2.0,
          "source": "NASA/CCMC Flare Scoreboard · CCMC ASSA",
          "quality": "published-comparison",
          "issued": "2026-11-08T00:00:00Z",
          "valid_start": "2026-11-08T00:00:00Z",
          "valid_end": "2026-11-08T12:00:00Z",
          "note": "Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI feed using the /data parameter schema.",
          "dataset_id": "ASSA_1_FULLDISK"
        },
        "ccmc_magpy_los": {
          "m1": 47.0,
          "x1": 11.0,
          "source": "NASA/CCMC Flare Scoreboard · CCMC MagPy HMI LOS",
          "quality": "published-comparison",
          "issued": "2026-11-08T00:13:18Z",
          "valid_start": "2026-11-07T21:00:00Z",
          "valid_end": "2026-11-08T21:00:00Z",
          "note": "Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI feed using the /data parameter schema.",
          "dataset_id": "MagPy-HMI-LOS_FULLDISK"
        },
        "ccmc_magpy": {
          "m1": 33.0,
          "x1": 17.0,
          "source": "NASA/CCMC Flare Scoreboard · CCMC MagPy SHARP",
          "quality": "published-comparison",
          "issued": "2026-11-08T02:01:42Z",
          "valid_start": "2026-11-07T23:00:00Z",
          "valid_end": "2026-11-08T23:00:00Z",
          "note": "Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI feed using the /data parameter schema.",
          "dataset_id": "MagPy_SHARP_HMI_CEA_FULLDISK"
        },
        "ccmc_sps": {
          "m1": null,
          "x1": 10.0,
          "source": "NASA/CCMC Flare Scoreboard · CCMC SPS",
          "quality": "published-comparison",
          "issued": "2026-11-07T17:00:00Z",
          "valid_start": "2026-11-07T17:00:00Z",
          "valid_end": "2026-11-08T17:00:00Z",
          "note": "Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI feed using the /data parameter schema.",
          "dataset_id": "SPS_FULLDISK"
        }
      }
    },
    {
      "id": "AR14564",
      "label": "AR 14564",
      "location": "N01W55",
      "mcintosh": "",
      "quality": {
        "level": "research",
        "message": "SHARP NRT record age 3.0 h; single-region HARP; |LON_FWT|=44.3°"
      },
      "members": {
        "sharpmag": {
          "m1": 0.4,
          "x1": 0.1,
          "source": "WXF sharp-mag-20260903-xstruct-history-v3 (independently calibrated magnetic M1/X1)",
          "quality": "research",
          "method": "sharp_magnetic",
          "component_id": "HARP14146"
        },
        "swpc": {
          "m1": 0.0,
          "x1": 0.0,
          "source": "NOAA/SWPC numbered-region flare forecast",
          "quality": "official-operational",
          "method": "official_swpc"
        }
      },
      "drivers": [
        "M1+: elevated mean free-energy density",
        "M1+: farther from disk center",
        "X1+ direct: lower absolute net current helicity",
        "X1+ direct: lower mean magnetic shear"
      ]
    },
    {
      "id": "AR14565",
      "label": "AR 14565",
      "location": "N13W31",
      "mcintosh": "HSX",
      "quality": {
        "level": "research",
        "message": "SHARP NRT record age 3.0 h; single-region HARP; |LON_FWT|=26.2°"
      },
      "members": {
        "sharpmag": {
          "m1": 2.2,
          "x1": 0.2,
          "source": "WXF sharp-mag-20260903-xstruct-history-v3 (independently calibrated magnetic M1/X1)",
          "quality": "research",
          "method": "sharp_magnetic",
          "component_id": "HARP14155"
        },
        "swpc": {
          "m1": 1.0,
          "x1": 1.0,
          "source": "NOAA/SWPC numbered-region flare forecast",
          "quality": "official-operational",
          "method": "official_swpc"
        },
        "mcstat": {
          "m1": 3.0,
          "x1": 0.0,
          "source": "SolarMonitor MCSTAT regional forecast",
          "quality": "published-comparison"
        },
        "mcevol": {
          "m1": 1.0,
          "x1": 0.0,
          "source": "SolarMonitor MCEVOL regional forecast",
          "quality": "published-comparison"
        }
      },
      "drivers": [
        "M1+: rising total unsigned flux",
        "M1+: falling mean magnetic shear",
        "X1+ direct: elevated absolute net current helicity",
        "X1+ direct: elevated mean magnetic shear"
      ]
    },
    {
      "id": "AR14566",
      "label": "AR 14566",
      "location": "S06E06",
      "mcintosh": "DKC",
      "quality": {
        "level": "research",
        "message": "SHARP NRT record age 3.0 h; shared 2-region HARP; |LON_FWT|=8.7°"
      },
      "members": {
        "sharpmag": {
          "m1": 61.5,
          "x1": 0.5,
          "source": "WXF sharp-mag-20260903-xstruct-history-v3 (independently calibrated magnetic M1/X1)",
          "quality": "research-shared-harp",
          "method": "sharp_magnetic",
          "component_id": "HARP14160"
        },
        "swpc": {
          "m1": 60.0,
          "x1": 20.0,
          "source": "NOAA/SWPC numbered-region flare forecast",
          "quality": "official-operational",
          "method": "official_swpc"
        },
        "mcstat": {
          "m1": 24.0,
          "x1": 2.0,
          "source": "SolarMonitor MCSTAT regional forecast",
          "quality": "published-comparison"
        }
      },
      "drivers": [
        "M1+: elevated active magnetic area",
        "M1+: elevated time since the last M1+ flare",
        "X1+ direct: elevated active magnetic area",
        "X1+ direct: elevated absolute net current helicity"
      ]
    },
    {
      "id": "AR14567",
      "label": "AR 14567",
      "location": "N18W83",
      "mcintosh": "HRX",
      "quality": {
        "level": "fallback",
        "message": "Numbered region is represented, but no accepted live SHARP vector was available; this is not a SHARP magnetic inference."
      },
      "members": {
        "sharpmag": {
          "m1": 2.0,
          "x1": 0.0,
          "source": "Bloomfield et al. (2012) McIntosh-Poisson coverage fallback",
          "quality": "research-coverage-fallback",
          "method": "morphology_fallback",
          "component_id": "AR14567-fallback"
        },
        "swpc": {
          "m1": 1.0,
          "x1": 1.0,
          "source": "NOAA/SWPC numbered-region flare forecast",
          "quality": "official-operational",
          "method": "official_swpc"
        },
        "mcstat": {
          "m1": 3.0,
          "x1": 0.0,
          "source": "SolarMonitor MCSTAT regional forecast",
          "quality": "published-comparison"
        },
        "mcevol": {
          "m1": 4.0,
          "x1": 0.0,
          "source": "SolarMonitor MCEVOL regional forecast",
          "quality": "published-comparison"
        }
      },
      "drivers": [
        "McIntosh HRX",
        "No accepted live single-region SHARP vector"
      ]
    },
    {
      "id": "AR14568",
      "label": "AR 14568",
      "location": "S09E25",
      "mcintosh": "AXX",
      "quality": {
        "level": "research",
        "message": "SHARP NRT record age 3.0 h; single-region HARP; |LON_FWT|=31.0°"
      },
      "members": {
        "sharpmag": {
          "m1": 0.4,
          "x1": 0.0,
          "source": "WXF sharp-mag-20260903-xstruct-history-v3 (independently calibrated magnetic M1/X1)",
          "quality": "research",
          "method": "sharp_magnetic",
          "component_id": "HARP14165"
        },
        "swpc": {
          "m1": 1.0,
          "x1": 1.0,
          "source": "NOAA/SWPC numbered-region flare forecast",
          "quality": "official-operational",
          "method": "official_swpc"
        },
        "mcstat": {
          "m1": 1.0,
          "x1": 0.0,
          "source": "SolarMonitor MCSTAT regional forecast",
          "quality": "published-comparison"
        }
      },
      "drivers": [
        "M1+: falling total unsigned flux",
        "M1+: elevated mean free-energy density",
        "X1+ direct: lower absolute net current helicity",
        "X1+ direct: falling absolute net current helicity"
      ]
    },
    {
      "id": "AR14569",
      "label": "AR 14569",
      "location": "S06W07",
      "mcintosh": "AXX",
      "quality": {
        "level": "research",
        "message": "SHARP NRT record age 3.0 h; shared 2-region HARP; |LON_FWT|=8.7°"
      },
      "members": {
        "sharpmag": {
          "m1": 14.6,
          "x1": 0.6,
          "source": "WXF sharp-mag-20260903-xstruct-history-v3 (independently calibrated magnetic M1/X1)",
          "quality": "research-shared-harp",
          "method": "sharp_magnetic",
          "component_id": "HARP14160"
        },
        "swpc": {
          "m1": 1.0,
          "x1": 1.0,
          "source": "NOAA/SWPC numbered-region flare forecast",
          "quality": "official-operational",
          "method": "official_swpc"
        },
        "mcstat": {
          "m1": 1.0,
          "x1": 0.0,
          "source": "SolarMonitor MCSTAT regional forecast",
          "quality": "published-comparison"
        }
      },
      "drivers": [
        "M1+: elevated active magnetic area",
        "M1+: lower mean free-energy density",
        "X1+ direct: elevated active magnetic area",
        "X1+ direct: elevated absolute net current helicity"
      ]
    },
    {
      "id": "AR14570",
      "label": "AR 14570",
      "location": "S13E47",
      "mcintosh": "AXX",
      "quality": {
        "level": "research",
        "message": "SHARP NRT record age 3.0 h; single-region HARP; |LON_FWT|=49.2°"
      },
      "members": {
        "sharpmag": {
          "m1": 0.2,
          "x1": 0.0,
          "source": "WXF sharp-mag-20260903-xstruct-history-v3 (independently calibrated magnetic M1/X1)",
          "quality": "research",
          "method": "sharp_magnetic",
          "component_id": "HARP14169"
        },
        "swpc": {
          "m1": 1.0,
          "x1": 1.0,
          "source": "NOAA/SWPC numbered-region flare forecast",
          "quality": "official-operational",
          "method": "official_swpc"
        },
        "mcstat": {
          "m1": 1.0,
          "x1": 0.0,
          "source": "SolarMonitor MCSTAT regional forecast",
          "quality": "published-comparison"
        }
      },
      "drivers": [
        "M1+: lower strong-gradient PIL flux",
        "M1+: rising total unsigned flux",
        "X1+ direct: lower strong-gradient PIL flux",
        "X1+ direct: rising active magnetic area"
      ]
    }
  ],
  "solar_monitor": {
    "source": "SolarMonitor",
    "source_url": "https://www.solarmonitor.org/forecast.php?date=20261107&region=&indexnum=1",
    "retrieved_at": "2026-11-08T02:33:54Z",
    "table_date": "2026-11-07",
    "valid_start": "2026-11-07T00:00:00Z",
    "valid_end": "2026-11-08T00:00:00Z",
    "wxf_valid_start": "2026-11-08T00:00:00Z",
    "wxf_valid_end": "2026-11-09T00:00:00Z",
    "window_alignment": "latest issue-date comparison; not asserted as an exact WXF target-window match",
    "regional_forecasts": 6,
    "full_disk_method": "maximum regional probability (dominant-region proxy)",
    "note": "Regional MCSTAT/MCEVOL values are reproduced from the latest issue-date SolarMonitor table. SolarMonitor does not publish a full-disk aggregate in this table; the dashboard uses each method's maximum published regional probability to avoid an independence-union inflation. The table's daily window is reported separately from WXF's next-calendar-day window; missing values remain missing."
  },
  "external_sources": {
    "generated_at": "2026-11-08T02:33:54Z",
    "script_version": "1.0.0",
    "sidc_direct": {
      "ok": true,
      "url": "https://www.sidc.be/WMO/FlareForecast.php",
      "issued": "2026-11-07T12:43:44Z",
      "m1": 0.0,
      "x1": 0.0
    },
    "ccmc_catalog": {
      "ok": true,
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/catalog",
      "datasets": 22
    },
    "ccmc_sidc": {
      "dataset_id": "SIDC_Operator_FULLDISK",
      "label": "SIDC Operator",
      "ok": false,
      "parser": "3.0.0",
      "info_url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/info?id=SIDC_Operator_FULLDISK",
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=SIDC_Operator_FULLDISK&time.min=2026-11-03T21%3A00%3A00.0&time.max=2026-11-08T21%3A00%3A00.0&format=json&options=fields.all",
      "schema_source": "data",
      "parameter_names": [
        "start_window",
        "end_window",
        "issue_time",
        "C",
        "M",
        "CPlus",
        "MPlus",
        "X",
        "C_uncertainty",
        "M_uncertainty",
        "CPlus_uncertainty",
        "MPlus_uncertainty",
        "X_uncertainty",
        "C_value_lower",
        "M_value_lower",
        "CPlus_value_lower",
        "MPlus_value_lower",
        "X_value_lower",
        "C_value_higher",
        "M_value_higher",
        "CPlus_value_higher",
        "MPlus_value_higher",
        "X_value_higher",
        "C_level",
        "M_level",
        "CPlus_level",
        "MPlus_level",
        "X_level"
      ],
      "m_parameter": "MPlus",
      "x_parameter": "X",
      "records": 2,
      "detail": "Forecast window does not meaningfully overlap target (2026-11-06T12:30:00Z to 2026-11-07T12:30:00Z)"
    },
    "ccmc_metoffice": {
      "dataset_id": "MO_TOT1_FULLDISK",
      "label": "Met Office (MOSWOC)",
      "ok": false,
      "parser": "3.0.0",
      "info_url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/info?id=MO_TOT1_FULLDISK",
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=MO_TOT1_FULLDISK&time.min=2026-11-03T21%3A00%3A00.0&time.max=2026-11-08T21%3A00%3A00.0&format=json&options=fields.all",
      "schema_source": "data",
      "parameter_names": [
        "start_window",
        "end_window",
        "issue_time",
        "C",
        "M",
        "CPlus",
        "MPlus",
        "X",
        "C_uncertainty",
        "M_uncertainty",
        "CPlus_uncertainty",
        "MPlus_uncertainty",
        "X_uncertainty",
        "C_value_lower",
        "M_value_lower",
        "CPlus_value_lower",
        "MPlus_value_lower",
        "X_value_lower",
        "C_value_higher",
        "M_value_higher",
        "CPlus_value_higher",
        "MPlus_value_higher",
        "X_value_higher",
        "C_level",
        "M_level",
        "CPlus_level",
        "MPlus_level",
        "X_level"
      ],
      "m_parameter": "MPlus",
      "x_parameter": "X",
      "records": 0,
      "detail": "No records in query window"
    },
    "ccmc_ccmc_amos": {
      "dataset_id": "AMOS_v1_FULLDISK",
      "label": "CCMC AMOS",
      "ok": true,
      "parser": "3.0.0",
      "info_url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/info?id=AMOS_v1_FULLDISK",
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=AMOS_v1_FULLDISK&time.min=2026-11-03T21%3A00%3A00.0&time.max=2026-11-08T21%3A00%3A00.0&format=json&options=fields.all",
      "schema_source": "data",
      "parameter_names": [
        "start_window",
        "end_window",
        "issue_time",
        "C",
        "M",
        "CPlus",
        "MPlus",
        "X",
        "C_uncertainty",
        "M_uncertainty",
        "CPlus_uncertainty",
        "MPlus_uncertainty",
        "X_uncertainty",
        "C_value_lower",
        "M_value_lower",
        "CPlus_value_lower",
        "MPlus_value_lower",
        "X_value_lower",
        "C_value_higher",
        "M_value_higher",
        "CPlus_value_higher",
        "MPlus_value_higher",
        "X_value_higher",
        "C_level",
        "M_level",
        "CPlus_level",
        "MPlus_level",
        "X_level"
      ],
      "m_parameter": "MPlus",
      "x_parameter": "X",
      "records": 5,
      "issued": "2026-11-08T00:30:00Z",
      "valid_start": "2026-11-08T00:00:00Z",
      "valid_end": "2026-11-09T00:00:00Z",
      "m1": null,
      "x1": 10.09,
      "selected_record": {
        "start_window": "2026-11-08T00:00:00.0Z",
        "end_window": "2026-11-09T00:00:00.0Z",
        "issue_time": "2026-11-08T00:30:00.0Z",
        "C": 0.95,
        "M": 0.4879,
        "CPlus": "-1",
        "MPlus": "-1",
        "X": 0.1009,
        "C_uncertainty": "-1",
        "M_uncertainty": "-1",
        "CPlus_uncertainty": "-1",
        "MPlus_uncertainty": "-1",
        "X_uncertainty": "-1",
        "C_value_lower": "-1",
        "M_value_lower": "-1",
        "CPlus_value_lower": "-1",
        "MPlus_value_lower": "-1",
        "X_value_lower": "-1",
        "C_value_higher": "-1",
        "M_value_higher": "-1",
        "CPlus_value_higher": "-1",
        "MPlus_value_higher": "-1",
        "X_value_higher": "-1",
        "C_level": "-1",
        "M_level": "-1",
        "CPlus_level": "-1",
        "MPlus_level": "-1",
        "X_level": "-1"
      }
    },
    "ccmc_ccmc_asap": {
      "dataset_id": "ASAP_1_FULLDISK",
      "label": "CCMC ASAP",
      "ok": false,
      "parser": "3.0.0",
      "info_url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/info?id=ASAP_1_FULLDISK",
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=ASAP_1_FULLDISK&time.min=2026-11-03T21%3A00%3A00.0&time.max=2026-11-08T21%3A00%3A00.0&format=json&options=fields.all",
      "schema_source": "data",
      "parameter_names": [
        "start_window",
        "end_window",
        "issue_time",
        "C",
        "M",
        "CPlus",
        "MPlus",
        "X",
        "C_uncertainty",
        "M_uncertainty",
        "CPlus_uncertainty",
        "MPlus_uncertainty",
        "X_uncertainty",
        "C_value_lower",
        "M_value_lower",
        "CPlus_value_lower",
        "MPlus_value_lower",
        "X_value_lower",
        "C_value_higher",
        "M_value_higher",
        "CPlus_value_higher",
        "MPlus_value_higher",
        "X_value_higher",
        "C_level",
        "M_level",
        "CPlus_level",
        "MPlus_level",
        "X_level"
      ],
      "m_parameter": "MPlus",
      "x_parameter": "X",
      "records": 0,
      "detail": "No records in query window"
    },
    "ccmc_ccmc_assa24": {
      "dataset_id": "ASSA_24H_1_FULLDISK",
      "label": "CCMC ASSA 24H",
      "ok": true,
      "parser": "3.0.0",
      "info_url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/info?id=ASSA_24H_1_FULLDISK",
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=ASSA_24H_1_FULLDISK&time.min=2026-11-03T21%3A00%3A00.0&time.max=2026-11-08T21%3A00%3A00.0&format=json&options=fields.all",
      "schema_source": "data",
      "parameter_names": [
        "start_window",
        "end_window",
        "issue_time",
        "C",
        "M",
        "CPlus",
        "MPlus",
        "X",
        "C_uncertainty",
        "M_uncertainty",
        "CPlus_uncertainty",
        "MPlus_uncertainty",
        "X_uncertainty",
        "C_value_lower",
        "M_value_lower",
        "CPlus_value_lower",
        "MPlus_value_lower",
        "X_value_lower",
        "C_value_higher",
        "M_value_higher",
        "CPlus_value_higher",
        "MPlus_value_higher",
        "X_value_higher",
        "C_level",
        "M_level",
        "CPlus_level",
        "MPlus_level",
        "X_level"
      ],
      "m_parameter": "MPlus",
      "x_parameter": "X",
      "records": 102,
      "issued": "2026-11-08T00:00:00Z",
      "valid_start": "2026-11-08T00:00:00Z",
      "valid_end": "2026-11-09T00:00:00Z",
      "m1": null,
      "x1": 3.96,
      "selected_record": {
        "start_window": "2026-11-08T00:00:00.0Z",
        "end_window": "2026-11-09T00:00:00.0Z",
        "issue_time": "2026-11-08T00:00:00.0Z",
        "C": 0.8064,
        "M": 0.2604,
        "CPlus": "-1",
        "MPlus": "-1",
        "X": 0.0396,
        "C_uncertainty": "-1",
        "M_uncertainty": "-1",
        "CPlus_uncertainty": "-1",
        "MPlus_uncertainty": "-1",
        "X_uncertainty": "-1",
        "C_value_lower": "-1",
        "M_value_lower": "-1",
        "CPlus_value_lower": "-1",
        "MPlus_value_lower": "-1",
        "X_value_lower": "-1",
        "C_value_higher": "-1",
        "M_value_higher": "-1",
        "CPlus_value_higher": "-1",
        "MPlus_value_higher": "-1",
        "X_value_higher": "-1",
        "C_level": "-1",
        "M_level": "-1",
        "CPlus_level": "-1",
        "MPlus_level": "-1",
        "X_level": "-1"
      }
    },
    "ccmc_ccmc_assa": {
      "dataset_id": "ASSA_1_FULLDISK",
      "label": "CCMC ASSA",
      "ok": true,
      "parser": "3.0.0",
      "info_url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/info?id=ASSA_1_FULLDISK",
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=ASSA_1_FULLDISK&time.min=2026-11-03T21%3A00%3A00.0&time.max=2026-11-08T21%3A00%3A00.0&format=json&options=fields.all",
      "schema_source": "data",
      "parameter_names": [
        "start_window",
        "end_window",
        "issue_time",
        "C",
        "M",
        "CPlus",
        "MPlus",
        "X",
        "C_uncertainty",
        "M_uncertainty",
        "CPlus_uncertainty",
        "MPlus_uncertainty",
        "X_uncertainty",
        "C_value_lower",
        "M_value_lower",
        "CPlus_value_lower",
        "MPlus_value_lower",
        "X_value_lower",
        "C_value_higher",
        "M_value_higher",
        "CPlus_value_higher",
        "MPlus_value_higher",
        "X_value_higher",
        "C_level",
        "M_level",
        "CPlus_level",
        "MPlus_level",
        "X_level"
      ],
      "m_parameter": "MPlus",
      "x_parameter": "X",
      "records": 102,
      "issued": "2026-11-08T00:00:00Z",
      "valid_start": "2026-11-08T00:00:00Z",
      "valid_end": "2026-11-08T12:00:00Z",
      "m1": null,
      "x1": 2.0,
      "selected_record": {
        "start_window": "2026-11-08T00:00:00.0Z",
        "end_window": "2026-11-08T12:00:00.0Z",
        "issue_time": "2026-11-08T00:00:00.0Z",
        "C": 0.56,
        "M": 0.14,
        "CPlus": "-1",
        "MPlus": "-1",
        "X": 0.02,
        "C_uncertainty": "-1",
        "M_uncertainty": "-1",
        "CPlus_uncertainty": "-1",
        "MPlus_uncertainty": "-1",
        "X_uncertainty": "-1",
        "C_value_lower": "-1",
        "M_value_lower": "-1",
        "CPlus_value_lower": "-1",
        "MPlus_value_lower": "-1",
        "X_value_lower": "-1",
        "C_value_higher": "-1",
        "M_value_higher": "-1",
        "CPlus_value_higher": "-1",
        "MPlus_value_higher": "-1",
        "X_value_higher": "-1",
        "C_level": "-1",
        "M_level": "-1",
        "CPlus_level": "-1",
        "MPlus_level": "-1",
        "X_level": "-1"
      }
    },
    "ccmc_ccmc_bom": {
      "dataset_id": "BoM_flare1_FULLDISK",
      "label": "BoM Flarecast",
      "ok": false,
      "parser": "3.0.0",
      "info_url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/info?id=BoM_flare1_FULLDISK",
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=BoM_flare1_FULLDISK&time.min=2026-11-03T21%3A00%3A00.0&time.max=2026-11-08T21%3A00%3A00.0&format=json&options=fields.all",
      "schema_source": "data",
      "parameter_names": [
        "start_window",
        "end_window",
        "issue_time",
        "C",
        "M",
        "CPlus",
        "MPlus",
        "X",
        "C_uncertainty",
        "M_uncertainty",
        "CPlus_uncertainty",
        "MPlus_uncertainty",
        "X_uncertainty",
        "C_value_lower",
        "M_value_lower",
        "CPlus_value_lower",
        "MPlus_value_lower",
        "X_value_lower",
        "C_value_higher",
        "M_value_higher",
        "CPlus_value_higher",
        "MPlus_value_higher",
        "X_value_higher",
        "C_level",
        "M_level",
        "CPlus_level",
        "MPlus_level",
        "X_level"
      ],
      "m_parameter": "MPlus",
      "x_parameter": "X",
      "records": 0,
      "detail": "No records in query window"
    },
    "ccmc_ccmc_mag4_fe": {
      "dataset_id": "MAG4_LOS_FEr_FULLDISK",
      "label": "NASA MAG4 Free Energy",
      "ok": false,
      "parser": "3.0.0",
      "info_url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/info?id=MAG4_LOS_FEr_FULLDISK",
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=MAG4_LOS_FEr_FULLDISK&time.min=2026-11-03T21%3A00%3A00.0&time.max=2026-11-08T21%3A00%3A00.0&format=json&options=fields.all",
      "schema_source": "data",
      "parameter_names": [
        "start_window",
        "end_window",
        "issue_time",
        "C",
        "M",
        "CPlus",
        "MPlus",
        "X",
        "C_uncertainty",
        "M_uncertainty",
        "CPlus_uncertainty",
        "MPlus_uncertainty",
        "X_uncertainty",
        "C_value_lower",
        "M_value_lower",
        "CPlus_value_lower",
        "MPlus_value_lower",
        "X_value_lower",
        "C_value_higher",
        "M_value_higher",
        "CPlus_value_higher",
        "MPlus_value_higher",
        "X_value_higher",
        "C_level",
        "M_level",
        "CPlus_level",
        "MPlus_level",
        "X_level"
      ],
      "m_parameter": "MPlus",
      "x_parameter": "X",
      "records": 0,
      "detail": "No records in query window"
    },
    "ccmc_ccmc_mag4": {
      "dataset_id": "MAG4_LOS_r_FULLDISK",
      "label": "NASA MAG4",
      "ok": false,
      "parser": "3.0.0",
      "info_url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/info?id=MAG4_LOS_r_FULLDISK",
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=MAG4_LOS_r_FULLDISK&time.min=2026-11-03T21%3A00%3A00.0&time.max=2026-11-08T21%3A00%3A00.0&format=json&options=fields.all",
      "schema_source": "data",
      "parameter_names": [
        "start_window",
        "end_window",
        "issue_time",
        "C",
        "M",
        "CPlus",
        "MPlus",
        "X",
        "C_uncertainty",
        "M_uncertainty",
        "CPlus_uncertainty",
        "MPlus_uncertainty",
        "X_uncertainty",
        "C_value_lower",
        "M_value_lower",
        "CPlus_value_lower",
        "MPlus_value_lower",
        "X_value_lower",
        "C_value_higher",
        "M_value_higher",
        "CPlus_value_higher",
        "MPlus_value_higher",
        "X_value_higher",
        "C_level",
        "M_level",
        "CPlus_level",
        "MPlus_level",
        "X_level"
      ],
      "m_parameter": "MPlus",
      "x_parameter": "X",
      "records": 0,
      "detail": "No records in query window"
    },
    "ccmc_ccmc_magpy_los": {
      "dataset_id": "MagPy-HMI-LOS_FULLDISK",
      "label": "CCMC MagPy HMI LOS",
      "ok": true,
      "parser": "3.0.0",
      "info_url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/info?id=MagPy-HMI-LOS_FULLDISK",
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=MagPy-HMI-LOS_FULLDISK&time.min=2026-11-03T21%3A00%3A00.0&time.max=2026-11-08T21%3A00%3A00.0&format=json&options=fields.all",
      "schema_source": "data",
      "parameter_names": [
        "start_window",
        "end_window",
        "issue_time",
        "C",
        "M",
        "CPlus",
        "MPlus",
        "X",
        "C_uncertainty",
        "M_uncertainty",
        "CPlus_uncertainty",
        "MPlus_uncertainty",
        "X_uncertainty",
        "C_value_lower",
        "M_value_lower",
        "CPlus_value_lower",
        "MPlus_value_lower",
        "X_value_lower",
        "C_value_higher",
        "M_value_higher",
        "CPlus_value_higher",
        "MPlus_value_higher",
        "X_value_higher",
        "C_level",
        "M_level",
        "CPlus_level",
        "MPlus_level",
        "X_level"
      ],
      "m_parameter": "MPlus",
      "x_parameter": "X",
      "records": 81,
      "issued": "2026-11-08T00:13:18Z",
      "valid_start": "2026-11-07T21:00:00Z",
      "valid_end": "2026-11-08T21:00:00Z",
      "m1": 47.0,
      "x1": 11.0,
      "selected_record": {
        "start_window": "2026-11-07T21:00:00.0Z",
        "end_window": "2026-11-08T21:00:00.0Z",
        "issue_time": "2026-11-08T00:13:18.0Z",
        "C": "-1",
        "M": "-1",
        "CPlus": "-1",
        "MPlus": 0.47,
        "X": 0.11,
        "C_uncertainty": "-1",
        "M_uncertainty": "-1",
        "CPlus_uncertainty": "-1",
        "MPlus_uncertainty": 0.088,
        "X_uncertainty": 0.161,
        "C_value_lower": "-1",
        "M_value_lower": "-1",
        "CPlus_value_lower": "-1",
        "MPlus_value_lower": "-1",
        "X_value_lower": "-1",
        "C_value_higher": "-1",
        "M_value_higher": "-1",
        "CPlus_value_higher": "-1",
        "MPlus_value_higher": "-1",
        "X_value_higher": "-1",
        "C_level": "-1",
        "M_level": "-1",
        "CPlus_level": "-1",
        "MPlus_level": "-1",
        "X_level": "-1"
      }
    },
    "ccmc_ccmc_magpy": {
      "dataset_id": "MagPy_SHARP_HMI_CEA_FULLDISK",
      "label": "CCMC MagPy SHARP",
      "ok": true,
      "parser": "3.0.0",
      "info_url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/info?id=MagPy_SHARP_HMI_CEA_FULLDISK",
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=MagPy_SHARP_HMI_CEA_FULLDISK&time.min=2026-11-03T21%3A00%3A00.0&time.max=2026-11-08T21%3A00%3A00.0&format=json&options=fields.all",
      "schema_source": "data",
      "parameter_names": [
        "start_window",
        "end_window",
        "issue_time",
        "C",
        "M",
        "CPlus",
        "MPlus",
        "X",
        "C_uncertainty",
        "M_uncertainty",
        "CPlus_uncertainty",
        "MPlus_uncertainty",
        "X_uncertainty",
        "C_value_lower",
        "M_value_lower",
        "CPlus_value_lower",
        "MPlus_value_lower",
        "X_value_lower",
        "C_value_higher",
        "M_value_higher",
        "CPlus_value_higher",
        "MPlus_value_higher",
        "X_value_higher",
        "C_level",
        "M_level",
        "CPlus_level",
        "MPlus_level",
        "X_level"
      ],
      "m_parameter": "MPlus",
      "x_parameter": "X",
      "records": 87,
      "issued": "2026-11-08T02:01:42Z",
      "valid_start": "2026-11-07T23:00:00Z",
      "valid_end": "2026-11-08T23:00:00Z",
      "m1": 33.0,
      "x1": 17.0,
      "selected_record": {
        "start_window": "2026-11-07T23:00:00.0Z",
        "end_window": "2026-11-08T23:00:00.0Z",
        "issue_time": "2026-11-08T02:01:42.0Z",
        "C": "-1",
        "M": "-1",
        "CPlus": "-1",
        "MPlus": 0.33,
        "X": 0.17,
        "C_uncertainty": "-1",
        "M_uncertainty": "-1",
        "CPlus_uncertainty": "-1",
        "MPlus_uncertainty": 0.025,
        "X_uncertainty": 0.063,
        "C_value_lower": "-1",
        "M_value_lower": "-1",
        "CPlus_value_lower": "-1",
        "MPlus_value_lower": "-1",
        "X_value_lower": "-1",
        "C_value_higher": "-1",
        "M_value_higher": "-1",
        "CPlus_value_higher": "-1",
        "MPlus_value_higher": "-1",
        "X_value_higher": "-1",
        "C_level": "-1",
        "M_level": "-1",
        "CPlus_level": "-1",
        "MPlus_level": "-1",
        "X_level": "-1"
      }
    },
    "ccmc_ccmc_sps": {
      "dataset_id": "SPS_FULLDISK",
      "label": "CCMC SPS",
      "ok": true,
      "parser": "3.0.0",
      "info_url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/info?id=SPS_FULLDISK",
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=SPS_FULLDISK&time.min=2026-11-03T21%3A00%3A00.0&time.max=2026-11-08T21%3A00%3A00.0&format=json&options=fields.all",
      "schema_source": "data",
      "parameter_names": [
        "start_window",
        "end_window",
        "issue_time",
        "C",
        "M",
        "CPlus",
        "MPlus",
        "X",
        "C_uncertainty",
        "M_uncertainty",
        "CPlus_uncertainty",
        "MPlus_uncertainty",
        "X_uncertainty",
        "C_value_lower",
        "M_value_lower",
        "CPlus_value_lower",
        "MPlus_value_lower",
        "X_value_lower",
        "C_value_higher",
        "M_value_higher",
        "CPlus_value_higher",
        "MPlus_value_higher",
        "X_value_higher",
        "C_level",
        "M_level",
        "CPlus_level",
        "MPlus_level",
        "X_level"
      ],
      "m_parameter": "MPlus",
      "x_parameter": "X",
      "records": 4,
      "issued": "2026-11-07T17:00:00Z",
      "valid_start": "2026-11-07T17:00:00Z",
      "valid_end": "2026-11-08T17:00:00Z",
      "m1": null,
      "x1": 10.0,
      "selected_record": {
        "start_window": "2026-11-07T17:00:00.0Z",
        "end_window": "2026-11-08T17:00:00.0Z",
        "issue_time": "2026-11-07T17:00:00.0Z",
        "C": 0.99,
        "M": 0.4,
        "CPlus": "-1",
        "MPlus": "-1",
        "X": 0.1,
        "C_uncertainty": "-1",
        "M_uncertainty": "-1",
        "CPlus_uncertainty": "-1",
        "MPlus_uncertainty": "-1",
        "X_uncertainty": "-1",
        "C_value_lower": "-1",
        "M_value_lower": "-1",
        "CPlus_value_lower": "-1",
        "MPlus_value_lower": "-1",
        "X_value_lower": "-1",
        "C_value_higher": "-1",
        "M_value_higher": "-1",
        "CPlus_value_higher": "-1",
        "MPlus_value_higher": "-1",
        "X_value_higher": "-1",
        "C_level": "-1",
        "M_level": "-1",
        "CPlus_level": "-1",
        "MPlus_level": "-1",
        "X_level": "-1"
      }
    },
    "ccmc_ccmc_daffs": {
      "ok": false,
      "label": "CCMC DAFFS",
      "dataset_id": null,
      "detail": "No matching full-disk dataset in current CCMC catalog"
    },
    "ccmc_ccmc_aeffort": {
      "ok": false,
      "label": "CCMC A-EFFort",
      "dataset_id": null,
      "detail": "No matching full-disk dataset in current CCMC catalog"
    },
    "flarecast": {
      "ok": false,
      "url": "https://api.flarecast.eu/api/prediction/flarecast_latest.xml",
      "detail": "ConnectTimeout: HTTPSConnectionPool(host='api.flarecast.eu', port=443): Max retries exceeded with url: / (Caused by ConnectTimeoutError(<HTTPSConnection(host='api.flarecast.eu', port=443) at 0x70be8772f390>, 'Connection to api.flarecast.eu timed out. (connect timeout=30)'))"
    },
    "swpc": {
      "ok": true,
      "detail": "Official benchmark refreshed independently of SHARP",
      "issued": "2026-11-07T22:00:00+00:00",
      "url": "https://services.swpc.noaa.gov/text/3-day-solar-geomag-predictions.txt"
    },
    "strict_parser_version": "5.0.0",
    "availability_policy": "Only current, positively identified forecasts that overlap the wall's target period are published. Missing, stale, retired, maintenance-mode, or non-overlapping providers remain unavailable rather than being replaced or assigned a synthetic probability.",
    "provider_catalog": [
      {
        "key": "sidc",
        "label": "SIDC Operator",
        "dataset_ids": [
          "SIDC_Operator_FULLDISK"
        ]
      },
      {
        "key": "metoffice",
        "label": "Met Office (MOSWOC)",
        "dataset_ids": [
          "MO_TOT1_FULLDISK"
        ]
      },
      {
        "key": "ccmc_amos",
        "label": "CCMC AMOS",
        "dataset_ids": [
          "AMOS_v1_FULLDISK"
        ]
      },
      {
        "key": "ccmc_asap",
        "label": "CCMC ASAP",
        "dataset_ids": [
          "ASAP_1_FULLDISK"
        ]
      },
      {
        "key": "ccmc_assa24",
        "label": "CCMC ASSA 24H",
        "dataset_ids": [
          "ASSA_24H_1_FULLDISK"
        ]
      },
      {
        "key": "ccmc_assa",
        "label": "CCMC ASSA",
        "dataset_ids": [
          "ASSA_1_FULLDISK"
        ]
      },
      {
        "key": "ccmc_bom",
        "label": "BoM Flarecast",
        "dataset_ids": [
          "BoM_flare1_FULLDISK"
        ]
      },
      {
        "key": "ccmc_mag4_fe",
        "label": "NASA MAG4 Free Energy",
        "dataset_ids": [
          "MAG4_LOS_FEr_FULLDISK"
        ]
      },
      {
        "key": "ccmc_mag4",
        "label": "NASA MAG4",
        "dataset_ids": [
          "MAG4_LOS_r_FULLDISK"
        ]
      },
      {
        "key": "ccmc_magpy_los",
        "label": "CCMC MagPy HMI LOS",
        "dataset_ids": [
          "MagPy-HMI-LOS_FULLDISK"
        ]
      },
      {
        "key": "ccmc_magpy",
        "label": "CCMC MagPy SHARP",
        "dataset_ids": [
          "MagPy_SHARP_HMI_CEA_FULLDISK"
        ]
      },
      {
        "key": "ccmc_sps",
        "label": "CCMC SPS",
        "dataset_ids": [
          "SPS_FULLDISK"
        ]
      },
      {
        "key": "ccmc_daffs",
        "label": "CCMC DAFFS",
        "dataset_ids": []
      },
      {
        "key": "ccmc_aeffort",
        "label": "CCMC A-EFFort",
        "dataset_ids": []
      },
      {
        "key": "flarecast",
        "label": "FLARECAST",
        "dataset_ids": []
      },
      {
        "key": "njit_solarflarenet",
        "label": "NJIT SolarFlareNet",
        "dataset_ids": [],
        "status": "web-product-only"
      },
      {
        "key": "inaf_oact",
        "label": "INAF-OACT",
        "dataset_ids": [],
        "status": "web-product-only"
      }
    ],
    "njit_solarflarenet": {
      "ok": false,
      "label": "NJIT SolarFlareNet",
      "url": "https://nature.njit.edu/solardb/index.html",
      "detail": "The public SolarDB tool is retained in the wall's source inventory, but this workflow has no stable unauthenticated machine-readable endpoint from which to reproduce its current probabilities."
    },
    "inaf_oact": {
      "ok": false,
      "label": "INAF-OACT",
      "url": "http://ssa.oact.inaf.it/oact/Flare_forecasting.php",
      "detail": "The OACT web product is retained in the wall's source inventory, but no stable current machine-readable feed is configured."
    },
    "excluded_duplicates": {
      "spaceweatherlive": "Intentionally excluded because it republishes operational SWPC probabilities already displayed by the wall.",
      "NOAA_1_FULLDISK": "Intentionally excluded from the CCMC rows because the primary SWPC forecast already appears as its own method."
    },
    "ccmc_catalog_entries": [
      {
        "id": "AMOS_v1_FULLDISK",
        "title": "AMOS_v1",
        "description": ""
      },
      {
        "id": "AMOS_v1_REGIONS",
        "title": "AMOS_v1",
        "description": ""
      },
      {
        "id": "ASAP_1_FULLDISK",
        "title": "ASAP_1",
        "description": ""
      },
      {
        "id": "ASAP_1_REGIONS",
        "title": "ASAP_1",
        "description": ""
      },
      {
        "id": "ASSA_1_FULLDISK",
        "title": "ASSA_1",
        "description": ""
      },
      {
        "id": "ASSA_1_REGIONS",
        "title": "ASSA_1",
        "description": ""
      },
      {
        "id": "ASSA_24H_1_FULLDISK",
        "title": "ASSA_24H_1",
        "description": ""
      },
      {
        "id": "ASSA_24H_1_REGIONS",
        "title": "ASSA_24H_1",
        "description": ""
      },
      {
        "id": "BoM_flare1_FULLDISK",
        "title": "Australian Bureau of Meteorology, Space Weather Services Flarecast automatic forecast",
        "description": ""
      },
      {
        "id": "BoM_flare1_REGIONS",
        "title": "Australian Bureau of Meteorology, Space Weather Services Flarecast automatic forecast",
        "description": ""
      },
      {
        "id": "MAG4_LOS_FEr_FULLDISK",
        "title": "MAG4 Using Line-of-Sight HMI magnetogram. Free energy only. Near-Real-Time data. [HMI-NRT]",
        "description": ""
      },
      {
        "id": "MAG4_LOS_FEr_REGIONS",
        "title": "MAG4 Using Line-of-Sight HMI magnetogram. Free energy only. Near-Real-Time data. [HMI-NRT]",
        "description": ""
      },
      {
        "id": "MAG4_LOS_r_FULLDISK",
        "title": "MAG4 Using Line-of-Sight HMI magnetogram. Free energy with flares. Near-Real-Time data. [WF-HMI-NRT]",
        "description": ""
      },
      {
        "id": "MAG4_LOS_r_REGIONS",
        "title": "MAG4 Using Line-of-Sight HMI magnetogram. Free energy with flares. Near-Real-Time data. [WF-HMI-NRT]",
        "description": ""
      },
      {
        "id": "MO_TOT1_FULLDISK",
        "title": "Met Office",
        "description": ""
      },
      {
        "id": "MagPy-HMI-LOS_FULLDISK",
        "title": "spase://CCMC/SimulationModel/MagPy/v3",
        "description": ""
      },
      {
        "id": "MagPy_SHARP_HMI_CEA_FULLDISK",
        "title": "spase://CCMC/SimulationModel/MagPy/v3",
        "description": ""
      },
      {
        "id": "NOAA_1_FULLDISK",
        "title": "NOAA_1",
        "description": ""
      },
      {
        "id": "NOAA_1_REGIONS",
        "title": "NOAA_1",
        "description": ""
      },
      {
        "id": "SIDC_Operator_FULLDISK",
        "title": "SIDC human operator moderated",
        "description": ""
      },
      {
        "id": "SIDC_Operator_REGIONS",
        "title": "SIDC human operator moderated",
        "description": ""
      },
      {
        "id": "SPS_FULLDISK",
        "title": "SPS Flare Scoreboard [SPS]",
        "description": ""
      }
    ]
  }
};
