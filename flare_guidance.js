/* Generated automatically by the SpaceWxOps WXF workflow. */
window.FLARE_GUIDANCE_PAYLOAD = {
  "schema_version": "5.0",
  "model_version": "sharp-mag-20260903-xstruct-history-v3",
  "script_version": "2.0.0",
  "operational": false,
  "probability_scale": "percent",
  "issued": "2026-09-03T21:00:00Z",
  "valid_start": "2026-09-04T00:00:00Z",
  "valid_end": "2026-09-05T00:00:00Z",
  "quality": {
    "level": "research",
    "message": "Daily WXF inference from a saved calibrated M1+ model and an independently calibrated magnetic/history X1+ model. Research/shadow guidance unless explicitly validated and marked operational."
  },
  "input": {
    "series": "hmi.sharp_cea_720s_nrt",
    "target_time": "2026-09-03T18:00:00Z",
    "latest_record": "2026-09-03T18:00:00Z",
    "oldest_retained_record": "2026-09-03T18:00:00Z",
    "raw_records": 2501,
    "retained_regions": 5,
    "mapping": {
      "skipped_multi_region_harps": 0,
      "skipped_unmapped_harps": 10,
      "expanded_rows": 7
    },
    "quality": {
      "input": 7,
      "rejected_longitude": 2,
      "after_longitude": 5,
      "quality_missing": 0,
      "quality_top_values": {
        "0x00010400": 5
      },
      "rejected_quality": 0,
      "after_quality": 5,
      "rejected_harp_merge": 0,
      "after_harp_merge": 5,
      "rejected_observer_velocity": 0,
      "after_observer_velocity": 5,
      "rejected_missing_mapping": 0,
      "after_mapping": 5,
      "min_finite_parameters": 12,
      "rejected_parameter_completeness": 0,
      "after_parameter_completeness": 5,
      "retained": 5
    },
    "flare_history": {
      "available": true,
      "source": "https://services.swpc.noaa.gov/json/edited_events.json",
      "events": 21,
      "m1_plus_events": 21,
      "x1_plus_events": 0
    },
    "swpc_full_disk": {
      "available": true,
      "source": "https://services.swpc.noaa.gov/text/3-day-solar-geomag-predictions.txt",
      "issued": "2026 Sep 02 2200 UTC",
      "valid_date": "2026-09-04"
    }
  },
  "wxf_full_disk": {
    "method": "union_of_unique_region_components",
    "formula": "1 - product(1 - regional probability)",
    "components": 5,
    "numbered_regions": 7,
    "sharp_regions": 5,
    "shared_harp_region_values": 4,
    "fallback_regions": 2,
    "unnumbered_or_farside_residual": false,
    "note": "Coverage aggregate, not a separately trained full-disk classifier. Shared HARP probabilities are included once."
  },
  "wxf_region_components": [
    {
      "component_id": "AR14518-fallback",
      "m1": 3.698416818063846,
      "x1": 0.24656112120425644
    },
    {
      "component_id": "AR14524-fallback",
      "m1": 3.0,
      "x1": 0.0
    },
    {
      "component_id": "HARP13922",
      "m1": 0.03985878726916839,
      "x1": 0.025812276954225215
    },
    {
      "component_id": "HARP13939",
      "m1": 0.3173090388584494,
      "x1": 0.042783457849236636
    },
    {
      "component_id": "HARP13945",
      "m1": 1.3311867722651762,
      "x1": 0.12268177501388892
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
        "5 SHARP region values; 2 fallbacks",
        "Regional probabilities combined as 1 - product(1 - p_i)",
        "Shared HARPs counted once in the full-disk aggregate",
        "No unnumbered or farside residual term"
      ],
      "members": {
        "sharpmag": {
          "m1": 8.2,
          "x1": 0.4,
          "source": "WXF sharp-mag-20260903-xstruct-history-v3 regional combination",
          "quality": "research",
          "method": "regional_union_with_explicit_fallbacks"
        },
        "swpc": {
          "m1": 15.0,
          "x1": 1.0,
          "source": "NOAA/SWPC 3-day whole-disk flare forecast",
          "quality": "official-operational",
          "method": "official_swpc"
        },
        "mcstat": {
          "m1": 3.0,
          "x1": 0.0,
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
          "issued": "2026-09-03T12:35:16Z",
          "valid_start": "2026-09-03T12:35:16Z",
          "valid_end": "2026-09-04T12:35:16Z",
          "note": "Human-operator-moderated global forecast published by SIDC."
        },
        "ccmc_amos": {
          "m1": null,
          "x1": 0.09,
          "source": "NASA/CCMC Flare Scoreboard · CCMC AMOS",
          "quality": "published-comparison",
          "issued": "2026-09-04T00:30:00Z",
          "valid_start": "2026-09-04T00:00:00Z",
          "valid_end": "2026-09-05T00:00:00Z",
          "note": "Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI feed using the /data parameter schema.",
          "dataset_id": "AMOS_v1_FULLDISK"
        },
        "ccmc_assa24": {
          "m1": null,
          "x1": 0.0,
          "source": "NASA/CCMC Flare Scoreboard · CCMC ASSA 24H",
          "quality": "published-comparison",
          "issued": "2026-09-04T00:00:00Z",
          "valid_start": "2026-09-04T00:00:00Z",
          "valid_end": "2026-09-05T00:00:00Z",
          "note": "Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI feed using the /data parameter schema.",
          "dataset_id": "ASSA_24H_1_FULLDISK"
        },
        "ccmc_assa": {
          "m1": null,
          "x1": 0.0,
          "source": "NASA/CCMC Flare Scoreboard · CCMC ASSA",
          "quality": "published-comparison",
          "issued": "2026-09-04T00:00:00Z",
          "valid_start": "2026-09-04T00:00:00Z",
          "valid_end": "2026-09-04T12:00:00Z",
          "note": "Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI feed using the /data parameter schema.",
          "dataset_id": "ASSA_1_FULLDISK"
        },
        "ccmc_magpy_los": {
          "m1": 6.0,
          "x1": 1.0,
          "source": "NASA/CCMC Flare Scoreboard · CCMC MagPy HMI LOS",
          "quality": "published-comparison",
          "issued": "2026-09-04T03:09:47Z",
          "valid_start": "2026-09-04T00:00:00Z",
          "valid_end": "2026-09-05T00:00:00Z",
          "note": "Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI feed using the /data parameter schema.",
          "dataset_id": "MagPy-HMI-LOS_FULLDISK"
        },
        "ccmc_magpy": {
          "m1": 2.0,
          "x1": 1.0,
          "source": "NASA/CCMC Flare Scoreboard · CCMC MagPy SHARP",
          "quality": "published-comparison",
          "issued": "2026-09-04T03:04:03Z",
          "valid_start": "2026-09-04T00:00:00Z",
          "valid_end": "2026-09-05T00:00:00Z",
          "note": "Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI feed using the /data parameter schema.",
          "dataset_id": "MagPy_SHARP_HMI_CEA_FULLDISK"
        },
        "ccmc_sps": {
          "m1": null,
          "x1": 1.0,
          "source": "NASA/CCMC Flare Scoreboard · CCMC SPS",
          "quality": "published-comparison",
          "issued": "2026-09-03T17:00:00Z",
          "valid_start": "2026-09-03T17:00:00Z",
          "valid_end": "2026-09-04T17:00:00Z",
          "note": "Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI feed using the /data parameter schema.",
          "dataset_id": "SPS_FULLDISK"
        }
      }
    },
    {
      "id": "AR14518",
      "label": "AR 14518",
      "location": "N08W65",
      "mcintosh": "",
      "quality": {
        "level": "fallback",
        "message": "Numbered region is represented, but no accepted live SHARP vector was available; this is not a SHARP magnetic inference."
      },
      "members": {
        "sharpmag": {
          "m1": 3.7,
          "x1": 0.2,
          "source": "WXF training-climatology coverage fallback",
          "quality": "research-coverage-fallback",
          "method": "morphology_fallback",
          "component_id": "AR14518-fallback"
        },
        "swpc": {
          "m1": 0.0,
          "x1": 0.0,
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
        "McIntosh class unavailable or absent from published table",
        "No accepted live single-region SHARP vector"
      ]
    },
    {
      "id": "AR14519",
      "label": "AR 14519",
      "location": "N27W59",
      "mcintosh": "",
      "quality": {
        "level": "research",
        "message": "SHARP NRT record age 3.0 h; shared 2-region HARP; |LON_FWT|=49.2°"
      },
      "members": {
        "sharpmag": {
          "m1": 0.0,
          "x1": 0.0,
          "source": "WXF sharp-mag-20260903-xstruct-history-v3 (independently calibrated magnetic M1/X1)",
          "quality": "research-shared-harp",
          "method": "sharp_magnetic",
          "component_id": "HARP13922"
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
        "M1+: lower active magnetic area",
        "M1+: lower strong-gradient PIL flux",
        "X1+ direct: lower active magnetic area",
        "X1+ direct: lower strong-gradient PIL flux"
      ]
    },
    {
      "id": "AR14520",
      "label": "AR 14520",
      "location": "S12W48",
      "mcintosh": "",
      "quality": {
        "level": "research",
        "message": "SHARP NRT record age 3.0 h; single-region HARP; |LON_FWT|=41.7°"
      },
      "members": {
        "sharpmag": {
          "m1": 0.3,
          "x1": 0.0,
          "source": "WXF sharp-mag-20260903-xstruct-history-v3 (independently calibrated magnetic M1/X1)",
          "quality": "research",
          "method": "sharp_magnetic",
          "component_id": "HARP13939"
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
        },
        "mcevol": {
          "m1": 0.0,
          "x1": 0.0,
          "source": "SolarMonitor MCEVOL regional forecast",
          "quality": "published-comparison"
        }
      },
      "drivers": [
        "M1+: elevated mean free-energy density",
        "M1+: lower active magnetic area",
        "X1+ direct: lower absolute net current helicity",
        "X1+ direct: lower active magnetic area"
      ]
    },
    {
      "id": "AR14521",
      "label": "AR 14521",
      "location": "N09E26",
      "mcintosh": "HSX",
      "quality": {
        "level": "research",
        "message": "SHARP NRT record age 3.0 h; shared 2-region HARP; |LON_FWT|=34.7°"
      },
      "members": {
        "sharpmag": {
          "m1": 1.3,
          "x1": 0.1,
          "source": "WXF sharp-mag-20260903-xstruct-history-v3 (independently calibrated magnetic M1/X1)",
          "quality": "research-shared-harp",
          "method": "sharp_magnetic",
          "component_id": "HARP13945"
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
          "m1": 0.0,
          "x1": 0.0,
          "source": "SolarMonitor MCEVOL regional forecast",
          "quality": "published-comparison"
        }
      },
      "drivers": [
        "M1+: elevated strong-gradient PIL flux",
        "M1+: elevated active magnetic area",
        "X1+ direct: elevated active magnetic area",
        "X1+ direct: lower absolute net current helicity"
      ]
    },
    {
      "id": "AR14522",
      "label": "AR 14522",
      "location": "N13W56",
      "mcintosh": "",
      "quality": {
        "level": "research",
        "message": "SHARP NRT record age 3.0 h; shared 2-region HARP; |LON_FWT|=49.2°"
      },
      "members": {
        "sharpmag": {
          "m1": 0.0,
          "x1": 0.0,
          "source": "WXF sharp-mag-20260903-xstruct-history-v3 (independently calibrated magnetic M1/X1)",
          "quality": "research-shared-harp",
          "method": "sharp_magnetic",
          "component_id": "HARP13922"
        },
        "swpc": {
          "m1": 0.0,
          "x1": 0.0,
          "source": "NOAA/SWPC numbered-region flare forecast",
          "quality": "official-operational",
          "method": "official_swpc"
        },
        "mcstat": {
          "m1": 1.0,
          "x1": 0.0,
          "source": "SolarMonitor MCSTAT regional forecast",
          "quality": "published-comparison"
        },
        "mcevol": {
          "m1": 0.0,
          "x1": 0.0,
          "source": "SolarMonitor MCEVOL regional forecast",
          "quality": "published-comparison"
        }
      },
      "drivers": [
        "M1+: lower active magnetic area",
        "M1+: lower strong-gradient PIL flux",
        "X1+ direct: lower active magnetic area",
        "X1+ direct: lower strong-gradient PIL flux"
      ]
    },
    {
      "id": "AR14523",
      "label": "AR 14523",
      "location": "N10E36",
      "mcintosh": "CAO",
      "quality": {
        "level": "research",
        "message": "SHARP NRT record age 3.0 h; shared 2-region HARP; |LON_FWT|=34.7°"
      },
      "members": {
        "sharpmag": {
          "m1": 1.3,
          "x1": 0.1,
          "source": "WXF sharp-mag-20260903-xstruct-history-v3 (independently calibrated magnetic M1/X1)",
          "quality": "research-shared-harp",
          "method": "sharp_magnetic",
          "component_id": "HARP13945"
        },
        "swpc": {
          "m1": 5.0,
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
        "M1+: elevated strong-gradient PIL flux",
        "M1+: elevated active magnetic area",
        "X1+ direct: elevated active magnetic area",
        "X1+ direct: lower absolute net current helicity"
      ]
    },
    {
      "id": "AR14524",
      "label": "AR 14524",
      "location": "N12E66",
      "mcintosh": "HAX",
      "quality": {
        "level": "fallback",
        "message": "Numbered region is represented, but no accepted live SHARP vector was available; this is not a SHARP magnetic inference."
      },
      "members": {
        "sharpmag": {
          "m1": 3.0,
          "x1": 0.0,
          "source": "Bloomfield et al. (2012) McIntosh-Poisson coverage fallback",
          "quality": "research-coverage-fallback",
          "method": "morphology_fallback",
          "component_id": "AR14524-fallback"
        },
        "swpc": {
          "m1": 10.0,
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
        }
      },
      "drivers": [
        "McIntosh HAX",
        "No accepted live single-region SHARP vector"
      ]
    }
  ],
  "solar_monitor": {
    "source": "SolarMonitor",
    "source_url": "https://www.solarmonitor.org/forecast.php?date=20260903&region=&indexnum=1",
    "retrieved_at": "2026-09-04T16:23:34Z",
    "table_date": "2026-09-03",
    "valid_start": "2026-09-03T00:00:00Z",
    "valid_end": "2026-09-04T00:00:00Z",
    "wxf_valid_start": "2026-09-04T00:00:00Z",
    "wxf_valid_end": "2026-09-05T00:00:00Z",
    "window_alignment": "latest issue-date comparison; not asserted as an exact WXF target-window match",
    "regional_forecasts": 6,
    "full_disk_method": "maximum regional probability (dominant-region proxy)",
    "note": "Regional MCSTAT/MCEVOL values are reproduced from the latest issue-date SolarMonitor table. SolarMonitor does not publish a full-disk aggregate in this table; the dashboard uses each method's maximum published regional probability to avoid an independence-union inflation. The table's daily window is reported separately from WXF's next-calendar-day window; missing values remain missing."
  },
  "external_sources": {
    "generated_at": "2026-09-04T16:23:34Z",
    "script_version": "1.0.0",
    "sidc_direct": {
      "ok": false,
      "url": "https://www.sidc.be/WMO/FlareForecast.php",
      "detail": "ConnectionError: HTTPSConnectionPool(host='www.sidc.be', port=443): Max retries exceeded with url: /WMO/FlareForecast.php (Caused by ProtocolError('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer')))"
    },
    "ccmc_catalog": {
      "ok": true,
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/catalog",
      "datasets": 22
    },
    "ccmc_sidc": {
      "dataset_id": "SIDC_Operator_FULLDISK",
      "label": "SIDC Operator",
      "ok": true,
      "parser": "3.0.0",
      "info_url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/info?id=SIDC_Operator_FULLDISK",
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=SIDC_Operator_FULLDISK&time.min=2026-08-30T21%3A00%3A00.0&time.max=2026-09-04T21%3A00%3A00.0&format=json&options=fields.all",
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
      "issued": "2026-09-03T12:35:25Z",
      "valid_start": "2026-09-03T12:30:00Z",
      "valid_end": "2026-09-04T12:30:00Z",
      "m1": 39.0,
      "x1": 1.0,
      "selected_record": {
        "start_window": "2026-09-03T12:30:00.0Z",
        "end_window": "2026-09-04T12:30:00.0Z",
        "issue_time": "2026-09-03T12:35:25.0Z",
        "C": "-1",
        "M": "-1",
        "CPlus": 0.82,
        "MPlus": 0.39,
        "X": 0.01,
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
        "CPlus_level": 0.82,
        "MPlus_level": 0.39,
        "X_level": 0.01
      }
    },
    "ccmc_metoffice": {
      "dataset_id": "MO_TOT1_FULLDISK",
      "label": "Met Office (MOSWOC)",
      "ok": false,
      "parser": "3.0.0",
      "info_url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/info?id=MO_TOT1_FULLDISK",
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=MO_TOT1_FULLDISK&time.min=2026-08-30T21%3A00%3A00.0&time.max=2026-09-04T21%3A00%3A00.0&format=json&options=fields.all",
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
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=AMOS_v1_FULLDISK&time.min=2026-08-30T21%3A00%3A00.0&time.max=2026-09-04T21%3A00%3A00.0&format=json&options=fields.all",
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
      "issued": "2026-09-04T00:30:00Z",
      "valid_start": "2026-09-04T00:00:00Z",
      "valid_end": "2026-09-05T00:00:00Z",
      "m1": null,
      "x1": 0.09,
      "selected_record": {
        "start_window": "2026-09-04T00:00:00.0Z",
        "end_window": "2026-09-05T00:00:00.0Z",
        "issue_time": "2026-09-04T00:30:00.0Z",
        "C": 0.2661,
        "M": 0.026,
        "CPlus": "-1",
        "MPlus": "-1",
        "X": 0.0009,
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
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=ASAP_1_FULLDISK&time.min=2026-08-30T21%3A00%3A00.0&time.max=2026-09-04T21%3A00%3A00.0&format=json&options=fields.all",
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
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=ASSA_24H_1_FULLDISK&time.min=2026-08-30T21%3A00%3A00.0&time.max=2026-09-04T21%3A00%3A00.0&format=json&options=fields.all",
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
      "records": 116,
      "issued": "2026-09-04T00:00:00Z",
      "valid_start": "2026-09-04T00:00:00Z",
      "valid_end": "2026-09-05T00:00:00Z",
      "m1": null,
      "x1": 0.0,
      "selected_record": {
        "start_window": "2026-09-04T00:00:00.0Z",
        "end_window": "2026-09-05T00:00:00.0Z",
        "issue_time": "2026-09-04T00:00:00.0Z",
        "C": 0.4524,
        "M": 0.0591,
        "CPlus": "-1",
        "MPlus": "-1",
        "X": 0,
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
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=ASSA_1_FULLDISK&time.min=2026-08-30T21%3A00%3A00.0&time.max=2026-09-04T21%3A00%3A00.0&format=json&options=fields.all",
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
      "records": 116,
      "issued": "2026-09-04T00:00:00Z",
      "valid_start": "2026-09-04T00:00:00Z",
      "valid_end": "2026-09-04T12:00:00Z",
      "m1": null,
      "x1": 0.0,
      "selected_record": {
        "start_window": "2026-09-04T00:00:00.0Z",
        "end_window": "2026-09-04T12:00:00.0Z",
        "issue_time": "2026-09-04T00:00:00.0Z",
        "C": 0.26,
        "M": 0.03,
        "CPlus": "-1",
        "MPlus": "-1",
        "X": 0,
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
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=BoM_flare1_FULLDISK&time.min=2026-08-30T21%3A00%3A00.0&time.max=2026-09-04T21%3A00%3A00.0&format=json&options=fields.all",
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
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=MAG4_LOS_FEr_FULLDISK&time.min=2026-08-30T21%3A00%3A00.0&time.max=2026-09-04T21%3A00%3A00.0&format=json&options=fields.all",
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
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=MAG4_LOS_r_FULLDISK&time.min=2026-08-30T21%3A00%3A00.0&time.max=2026-09-04T21%3A00%3A00.0&format=json&options=fields.all",
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
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=MagPy-HMI-LOS_FULLDISK&time.min=2026-08-30T21%3A00%3A00.0&time.max=2026-09-04T21%3A00%3A00.0&format=json&options=fields.all",
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
      "issued": "2026-09-04T03:09:47Z",
      "valid_start": "2026-09-04T00:00:00Z",
      "valid_end": "2026-09-05T00:00:00Z",
      "m1": 6.0,
      "x1": 1.0,
      "selected_record": {
        "start_window": "2026-09-04T00:00:00.0Z",
        "end_window": "2026-09-05T00:00:00.0Z",
        "issue_time": "2026-09-04T03:09:47.0Z",
        "C": "-1",
        "M": "-1",
        "CPlus": "-1",
        "MPlus": 0.06,
        "X": 0.01,
        "C_uncertainty": "-1",
        "M_uncertainty": "-1",
        "CPlus_uncertainty": "-1",
        "MPlus_uncertainty": 0.01,
        "X_uncertainty": 0.01,
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
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=MagPy_SHARP_HMI_CEA_FULLDISK&time.min=2026-08-30T21%3A00%3A00.0&time.max=2026-09-04T21%3A00%3A00.0&format=json&options=fields.all",
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
      "records": 99,
      "issued": "2026-09-04T03:04:03Z",
      "valid_start": "2026-09-04T00:00:00Z",
      "valid_end": "2026-09-05T00:00:00Z",
      "m1": 2.0,
      "x1": 1.0,
      "selected_record": {
        "start_window": "2026-09-04T00:00:00.0Z",
        "end_window": "2026-09-05T00:00:00.0Z",
        "issue_time": "2026-09-04T03:04:03.0Z",
        "C": "-1",
        "M": "-1",
        "CPlus": "-1",
        "MPlus": 0.02,
        "X": 0.01,
        "C_uncertainty": "-1",
        "M_uncertainty": "-1",
        "CPlus_uncertainty": "-1",
        "MPlus_uncertainty": 0.01,
        "X_uncertainty": 0.01,
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
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=SPS_FULLDISK&time.min=2026-08-30T21%3A00%3A00.0&time.max=2026-09-04T21%3A00%3A00.0&format=json&options=fields.all",
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
      "issued": "2026-09-03T17:00:00Z",
      "valid_start": "2026-09-03T17:00:00Z",
      "valid_end": "2026-09-04T17:00:00Z",
      "m1": null,
      "x1": 1.0,
      "selected_record": {
        "start_window": "2026-09-03T17:00:00.0Z",
        "end_window": "2026-09-04T17:00:00.0Z",
        "issue_time": "2026-09-03T17:00:00.0Z",
        "C": 0.99,
        "M": 0.55,
        "CPlus": "-1",
        "MPlus": "-1",
        "X": 0.01,
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
      "http_status": 200,
      "content_length": 49,
      "detail": "XML contained no parseable current M/X probabilities",
      "candidate_count": 0
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
