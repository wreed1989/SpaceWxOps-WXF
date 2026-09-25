/* Generated automatically by the SpaceWxOps WXF workflow. */
window.FLARE_GUIDANCE_PAYLOAD = {
  "schema_version": "5.0",
  "model_version": "sharp-mag-20260903-xstruct-history-v3",
  "script_version": "2.0.0",
  "operational": false,
  "probability_scale": "percent",
  "issued": "2026-09-24T21:00:00Z",
  "valid_start": "2026-09-25T00:00:00Z",
  "valid_end": "2026-09-26T00:00:00Z",
  "quality": {
    "level": "degraded",
    "message": "WXF input refresh unavailable; prior published WXF probabilities retained."
  },
  "input": {
    "series": "hmi.sharp_cea_720s_nrt",
    "target_time": "2026-09-24T18:00:00Z",
    "latest_record": "2026-09-24T18:00:00Z",
    "oldest_retained_record": "2026-09-24T18:00:00Z",
    "raw_records": 1201,
    "retained_regions": 4,
    "mapping": {
      "skipped_multi_region_harps": 0,
      "skipped_unmapped_harps": 6,
      "expanded_rows": 9
    },
    "quality": {
      "input": 9,
      "rejected_longitude": 4,
      "after_longitude": 5,
      "quality_missing": 0,
      "quality_top_values": {
        "0x00011400": 4,
        "0x00000400": 1
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
      "events": 10,
      "m1_plus_events": 10,
      "x1_plus_events": 0
    },
    "swpc_full_disk": {
      "available": true,
      "source": "https://services.swpc.noaa.gov/text/3-day-solar-geomag-predictions.txt",
      "issued": "2026-09-24T22:00:00+00:00",
      "valid_date": "2026-09-25"
    },
    "attempted_target_time": "2026-09-24T18:00:00Z",
    "fallback_from_previous_cycle": true
  },
  "wxf_full_disk": {
    "method": "union_of_unique_region_components",
    "formula": "1 - product(1 - regional probability)",
    "components": 9,
    "numbered_regions": 10,
    "sharp_regions": 4,
    "shared_harp_region_values": 2,
    "fallback_regions": 6,
    "unnumbered_or_farside_residual": false,
    "note": "Coverage aggregate, not a separately trained full-disk classifier. Shared HARP probabilities are included once. The product formula assumes independent components and is not a validated full-disk calibration."
  },
  "wxf_region_components": [
    {
      "component_id": "AR14534-fallback",
      "m1": 3.0,
      "x1": 0.0
    },
    {
      "component_id": "AR14537-fallback",
      "m1": 7.000000000000001,
      "x1": 0.0
    },
    {
      "component_id": "AR14538-fallback",
      "m1": 12.0,
      "x1": 0.0
    },
    {
      "component_id": "AR14540-fallback",
      "m1": 3.698416818063846,
      "x1": 0.24656112120425644
    },
    {
      "component_id": "AR14541-fallback",
      "m1": 3.698416818063846,
      "x1": 0.24656112120425644
    },
    {
      "component_id": "AR14542-fallback",
      "m1": 1.0,
      "x1": 0.0
    },
    {
      "component_id": "HARP14026",
      "m1": 3.4837340085768886,
      "x1": 0.36717918075134753
    },
    {
      "component_id": "HARP14028",
      "m1": 1.592616525320538,
      "x1": 0.1534327181130257
    },
    {
      "component_id": "HARP14033",
      "m1": 3.2905062795035724,
      "x1": 0.32018480451015957
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
        "10 numbered active regions represented",
        "4 SHARP region values; 6 fallbacks",
        "Regional probabilities combined as 1 - product(1 - p_i)",
        "Shared HARPs counted once in the full-disk aggregate",
        "No unnumbered or farside residual term"
      ],
      "members": {
        "sharpmag": {
          "m1": 33.1,
          "x1": 1.3,
          "source": "WXF sharp-mag-20260903-xstruct-history-v3 regional combination",
          "quality": "stale-fallback",
          "method": "regional_union_with_explicit_fallbacks",
          "issued": "2026-09-24T21:00:00Z",
          "note": "Previous published WXF magnetic probability retained because the current JSOC/SHARP query timed out after three attempts.",
          "valid_start": "2026-09-25T00:00:00+00:00",
          "valid_end": "2026-09-26T00:00:00+00:00"
        },
        "mcstat": {
          "m1": 16.0,
          "x1": 2.0,
          "source": "SolarMonitor MCSTAT dominant-region proxy (maximum of 9 regional forecasts)",
          "quality": "published-comparison"
        },
        "mcevol": {
          "m1": 10.0,
          "x1": 0.0,
          "source": "SolarMonitor MCEVOL dominant-region proxy (maximum of 9 regional forecasts)",
          "quality": "published-comparison"
        },
        "sidc": {
          "m1": 0.0,
          "x1": 0.0,
          "source": "SIDC 24-hour Global Flare Forecast",
          "quality": "published-comparison",
          "issued": "2026-09-25T12:06:43Z",
          "valid_start": "2026-09-25T12:06:43Z",
          "valid_end": "2026-09-26T12:06:43Z",
          "note": "Human-operator-moderated global forecast published by SIDC."
        },
        "ccmc_amos": {
          "m1": null,
          "x1": 0.12,
          "source": "NASA/CCMC Flare Scoreboard · CCMC AMOS",
          "quality": "published-comparison",
          "issued": "2026-09-25T00:30:00Z",
          "valid_start": "2026-09-25T00:00:00Z",
          "valid_end": "2026-09-26T00:00:00Z",
          "note": "Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI feed using the /data parameter schema.",
          "dataset_id": "AMOS_v1_FULLDISK"
        },
        "ccmc_assa24": {
          "m1": null,
          "x1": 0.0,
          "source": "NASA/CCMC Flare Scoreboard · CCMC ASSA 24H",
          "quality": "published-comparison",
          "issued": "2026-09-25T00:00:00Z",
          "valid_start": "2026-09-25T00:00:00Z",
          "valid_end": "2026-09-26T00:00:00Z",
          "note": "Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI feed using the /data parameter schema.",
          "dataset_id": "ASSA_24H_1_FULLDISK"
        },
        "ccmc_assa": {
          "m1": null,
          "x1": 0.0,
          "source": "NASA/CCMC Flare Scoreboard · CCMC ASSA",
          "quality": "published-comparison",
          "issued": "2026-09-25T00:00:00Z",
          "valid_start": "2026-09-25T00:00:00Z",
          "valid_end": "2026-09-25T12:00:00Z",
          "note": "Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI feed using the /data parameter schema.",
          "dataset_id": "ASSA_1_FULLDISK"
        },
        "ccmc_magpy_los": {
          "m1": 2.0,
          "x1": 1.0,
          "source": "NASA/CCMC Flare Scoreboard · CCMC MagPy HMI LOS",
          "quality": "published-comparison",
          "issued": "2026-09-25T03:16:01Z",
          "valid_start": "2026-09-25T00:00:00Z",
          "valid_end": "2026-09-26T00:00:00Z",
          "note": "Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI feed using the /data parameter schema.",
          "dataset_id": "MagPy-HMI-LOS_FULLDISK"
        },
        "ccmc_magpy": {
          "m1": 5.0,
          "x1": 4.0,
          "source": "NASA/CCMC Flare Scoreboard · CCMC MagPy SHARP",
          "quality": "published-comparison",
          "issued": "2026-09-25T03:02:14Z",
          "valid_start": "2026-09-25T00:00:00Z",
          "valid_end": "2026-09-26T00:00:00Z",
          "note": "Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI feed using the /data parameter schema.",
          "dataset_id": "MagPy_SHARP_HMI_CEA_FULLDISK"
        },
        "ccmc_sps": {
          "m1": null,
          "x1": 1.0,
          "source": "NASA/CCMC Flare Scoreboard · CCMC SPS",
          "quality": "published-comparison",
          "issued": "2026-09-24T17:00:00Z",
          "valid_start": "2026-09-24T17:00:00Z",
          "valid_end": "2026-09-25T17:00:00Z",
          "note": "Probability reproduced from the NASA/CCMC Flare Scoreboard HAPI feed using the /data parameter schema.",
          "dataset_id": "SPS_FULLDISK"
        },
        "swpc": {
          "m1": 20.0,
          "x1": 1.0,
          "source": "NOAA/SWPC 3-day whole-disk flare forecast",
          "quality": "official-operational",
          "method": "official_swpc",
          "issued": "2026-09-24T22:00:00+00:00",
          "valid_start": "2026-09-25T00:00:00+00:00",
          "valid_end": "2026-09-26T00:00:00+00:00"
        }
      }
    },
    {
      "id": "AR14533",
      "label": "AR 14533",
      "location": "S14E09",
      "mcintosh": "HRX",
      "quality": {
        "level": "research",
        "message": "SHARP NRT record age 3.0 h; shared 2-region HARP; |LON_FWT|=13.2°"
      },
      "members": {
        "sharpmag": {
          "m1": 1.6,
          "x1": 0.2,
          "source": "WXF sharp-mag-20260903-xstruct-history-v3 (independently calibrated magnetic M1/X1)",
          "quality": "stale-fallback",
          "method": "sharp_magnetic",
          "component_id": "HARP14028",
          "issued": "2026-09-24T21:00:00Z",
          "note": "Previous published WXF magnetic probability retained because the current JSOC/SHARP query timed out after three attempts.",
          "valid_start": "2026-09-25T00:00:00+00:00",
          "valid_end": "2026-09-26T00:00:00+00:00"
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
        },
        "swpc": {
          "m1": 1.0,
          "x1": 1.0,
          "source": "SWPC regional forecast as displayed by SolarMonitor",
          "quality": "published-comparison"
        }
      },
      "drivers": [
        "M1+: rising total unsigned flux",
        "M1+: rising total unsigned current helicity",
        "X1+ direct: rising total unsigned current helicity",
        "X1+ direct: rising active magnetic area"
      ]
    },
    {
      "id": "AR14534",
      "label": "AR 14534",
      "location": "N11W61",
      "mcintosh": "CAO",
      "quality": {
        "level": "fallback",
        "message": "Numbered region is represented, but no accepted live SHARP vector was available; this is not a SHARP magnetic inference."
      },
      "members": {
        "sharpmag": {
          "m1": 3.0,
          "x1": 0.0,
          "source": "Bloomfield et al. (2012) McIntosh-Poisson coverage fallback",
          "quality": "stale-fallback",
          "method": "morphology_fallback",
          "component_id": "AR14534-fallback",
          "issued": "2026-09-24T21:00:00Z",
          "note": "Previous published WXF magnetic probability retained because the current JSOC/SHARP query timed out after three attempts.",
          "valid_start": "2026-09-25T00:00:00+00:00",
          "valid_end": "2026-09-26T00:00:00+00:00"
        },
        "mcstat": {
          "m1": 16.0,
          "x1": 2.0,
          "source": "SolarMonitor MCSTAT regional forecast",
          "quality": "published-comparison"
        },
        "mcevol": {
          "m1": 10.0,
          "x1": 0.0,
          "source": "SolarMonitor MCEVOL regional forecast",
          "quality": "published-comparison"
        },
        "swpc": {
          "m1": 10.0,
          "x1": 1.0,
          "source": "SWPC regional forecast as displayed by SolarMonitor",
          "quality": "published-comparison"
        }
      },
      "drivers": [
        "McIntosh CAO",
        "No accepted live single-region SHARP vector"
      ]
    },
    {
      "id": "AR14535",
      "label": "AR 14535",
      "location": "N12E21",
      "mcintosh": "DSO",
      "quality": {
        "level": "research",
        "message": "SHARP NRT record age 3.0 h; single-region HARP; |LON_FWT|=28.0°"
      },
      "members": {
        "sharpmag": {
          "m1": 3.3,
          "x1": 0.3,
          "source": "WXF sharp-mag-20260903-xstruct-history-v3 (independently calibrated magnetic M1/X1)",
          "quality": "stale-fallback",
          "method": "sharp_magnetic",
          "component_id": "HARP14033",
          "issued": "2026-09-24T21:00:00Z",
          "note": "Previous published WXF magnetic probability retained because the current JSOC/SHARP query timed out after three attempts.",
          "valid_start": "2026-09-25T00:00:00+00:00",
          "valid_end": "2026-09-26T00:00:00+00:00"
        },
        "mcstat": {
          "m1": 6.0,
          "x1": 0.0,
          "source": "SolarMonitor MCSTAT regional forecast",
          "quality": "published-comparison"
        },
        "mcevol": {
          "m1": 0.0,
          "x1": 0.0,
          "source": "SolarMonitor MCEVOL regional forecast",
          "quality": "published-comparison"
        },
        "swpc": {
          "m1": 1.0,
          "x1": 1.0,
          "source": "SWPC regional forecast as displayed by SolarMonitor",
          "quality": "published-comparison"
        }
      },
      "drivers": [
        "M1+: elevated active magnetic area",
        "M1+: falling total unsigned flux",
        "X1+ direct: elevated active magnetic area",
        "X1+ direct: elevated absolute net current helicity"
      ]
    },
    {
      "id": "AR14536",
      "label": "AR 14536",
      "location": "N03W39",
      "mcintosh": "DSI",
      "quality": {
        "level": "research",
        "message": "SHARP NRT record age 3.0 h; single-region HARP; |LON_FWT|=36.7°"
      },
      "members": {
        "sharpmag": {
          "m1": 3.5,
          "x1": 0.4,
          "source": "WXF sharp-mag-20260903-xstruct-history-v3 (independently calibrated magnetic M1/X1)",
          "quality": "stale-fallback",
          "method": "sharp_magnetic",
          "component_id": "HARP14026",
          "issued": "2026-09-24T21:00:00Z",
          "note": "Previous published WXF magnetic probability retained because the current JSOC/SHARP query timed out after three attempts.",
          "valid_start": "2026-09-25T00:00:00+00:00",
          "valid_end": "2026-09-26T00:00:00+00:00"
        },
        "mcstat": {
          "m1": 12.0,
          "x1": 0.0,
          "source": "SolarMonitor MCSTAT regional forecast",
          "quality": "published-comparison"
        },
        "mcevol": {
          "m1": 7.0,
          "x1": 0.0,
          "source": "SolarMonitor MCEVOL regional forecast",
          "quality": "published-comparison"
        },
        "swpc": {
          "m1": 5.0,
          "x1": 1.0,
          "source": "SWPC regional forecast as displayed by SolarMonitor",
          "quality": "published-comparison"
        }
      },
      "drivers": [
        "M1+: elevated active magnetic area",
        "M1+: elevated strong-gradient PIL flux",
        "X1+ direct: elevated absolute net current helicity",
        "X1+ direct: elevated active magnetic area"
      ]
    },
    {
      "id": "AR14537",
      "label": "AR 14537",
      "location": "N07W53",
      "mcintosh": "DAO",
      "quality": {
        "level": "fallback",
        "message": "Numbered region is represented, but no accepted live SHARP vector was available; this is not a SHARP magnetic inference."
      },
      "members": {
        "sharpmag": {
          "m1": 7.0,
          "x1": 0.0,
          "source": "Bloomfield et al. (2012) McIntosh-Poisson coverage fallback",
          "quality": "stale-fallback",
          "method": "morphology_fallback",
          "component_id": "AR14537-fallback",
          "issued": "2026-09-24T21:00:00Z",
          "note": "Previous published WXF magnetic probability retained because the current JSOC/SHARP query timed out after three attempts.",
          "valid_start": "2026-09-25T00:00:00+00:00",
          "valid_end": "2026-09-26T00:00:00+00:00"
        },
        "mcstat": {
          "m1": 12.0,
          "x1": 2.0,
          "source": "SolarMonitor MCSTAT regional forecast",
          "quality": "published-comparison"
        },
        "swpc": {
          "m1": 5.0,
          "x1": 1.0,
          "source": "SWPC regional forecast as displayed by SolarMonitor",
          "quality": "published-comparison"
        }
      },
      "drivers": [
        "McIntosh DAO",
        "No accepted live single-region SHARP vector"
      ]
    },
    {
      "id": "AR14538",
      "label": "AR 14538",
      "location": "N11W49",
      "mcintosh": "DSI",
      "quality": {
        "level": "fallback",
        "message": "Numbered region is represented, but no accepted live SHARP vector was available; this is not a SHARP magnetic inference."
      },
      "members": {
        "sharpmag": {
          "m1": 12.0,
          "x1": 0.0,
          "source": "Bloomfield et al. (2012) McIntosh-Poisson coverage fallback",
          "quality": "stale-fallback",
          "method": "morphology_fallback",
          "component_id": "AR14538-fallback",
          "issued": "2026-09-24T21:00:00Z",
          "note": "Previous published WXF magnetic probability retained because the current JSOC/SHARP query timed out after three attempts.",
          "valid_start": "2026-09-25T00:00:00+00:00",
          "valid_end": "2026-09-26T00:00:00+00:00"
        },
        "mcstat": {
          "m1": 12.0,
          "x1": 2.0,
          "source": "SolarMonitor MCSTAT regional forecast",
          "quality": "published-comparison"
        },
        "swpc": {
          "m1": 5.0,
          "x1": 1.0,
          "source": "SWPC regional forecast as displayed by SolarMonitor",
          "quality": "published-comparison"
        }
      },
      "drivers": [
        "McIntosh DSI",
        "No accepted live single-region SHARP vector"
      ]
    },
    {
      "id": "AR14539",
      "label": "AR 14539",
      "location": "S09W01",
      "mcintosh": "AXX",
      "quality": {
        "level": "research",
        "message": "SHARP NRT record age 3.0 h; shared 2-region HARP; |LON_FWT|=13.2°"
      },
      "members": {
        "sharpmag": {
          "m1": 1.6,
          "x1": 0.2,
          "source": "WXF sharp-mag-20260903-xstruct-history-v3 (independently calibrated magnetic M1/X1)",
          "quality": "stale-fallback",
          "method": "sharp_magnetic",
          "component_id": "HARP14028",
          "issued": "2026-09-24T21:00:00Z",
          "note": "Previous published WXF magnetic probability retained because the current JSOC/SHARP query timed out after three attempts.",
          "valid_start": "2026-09-25T00:00:00+00:00",
          "valid_end": "2026-09-26T00:00:00+00:00"
        },
        "mcstat": {
          "m1": 7.0,
          "x1": 1.0,
          "source": "SolarMonitor MCSTAT regional forecast",
          "quality": "published-comparison"
        },
        "mcevol": {
          "m1": 4.0,
          "x1": 0.0,
          "source": "SolarMonitor MCEVOL regional forecast",
          "quality": "published-comparison"
        },
        "swpc": {
          "m1": 5.0,
          "x1": 1.0,
          "source": "SWPC regional forecast as displayed by SolarMonitor",
          "quality": "published-comparison"
        }
      },
      "drivers": [
        "M1+: rising total unsigned flux",
        "M1+: rising total unsigned current helicity",
        "X1+ direct: rising total unsigned current helicity",
        "X1+ direct: rising active magnetic area"
      ]
    },
    {
      "id": "AR14540",
      "label": "AR 14540",
      "location": "S12W77",
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
          "quality": "stale-fallback",
          "method": "morphology_fallback",
          "component_id": "AR14540-fallback",
          "issued": "2026-09-24T21:00:00Z",
          "note": "Previous published WXF magnetic probability retained because the current JSOC/SHARP query timed out after three attempts.",
          "valid_start": "2026-09-25T00:00:00+00:00",
          "valid_end": "2026-09-26T00:00:00+00:00"
        },
        "mcstat": {
          "m1": 1.0,
          "x1": 0.0,
          "source": "SolarMonitor MCSTAT regional forecast",
          "quality": "published-comparison"
        },
        "mcevol": {
          "m1": 1.0,
          "x1": 0.0,
          "source": "SolarMonitor MCEVOL regional forecast",
          "quality": "published-comparison"
        },
        "swpc": {
          "m1": 1.0,
          "x1": 1.0,
          "source": "SWPC regional forecast as displayed by SolarMonitor",
          "quality": "published-comparison"
        }
      },
      "drivers": [
        "McIntosh class unavailable or absent from published table",
        "No accepted live single-region SHARP vector"
      ]
    },
    {
      "id": "AR14541",
      "label": "AR 14541",
      "location": "S05W82",
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
          "quality": "stale-fallback",
          "method": "morphology_fallback",
          "component_id": "AR14541-fallback",
          "issued": "2026-09-24T21:00:00Z",
          "note": "Previous published WXF magnetic probability retained because the current JSOC/SHARP query timed out after three attempts.",
          "valid_start": "2026-09-25T00:00:00+00:00",
          "valid_end": "2026-09-26T00:00:00+00:00"
        },
        "mcstat": {
          "m1": 1.0,
          "x1": 0.0,
          "source": "SolarMonitor MCSTAT regional forecast",
          "quality": "published-comparison"
        },
        "swpc": {
          "m1": 1.0,
          "x1": 1.0,
          "source": "SWPC regional forecast as displayed by SolarMonitor",
          "quality": "published-comparison"
        }
      },
      "drivers": [
        "McIntosh class unavailable or absent from published table",
        "No accepted live single-region SHARP vector"
      ]
    },
    {
      "id": "AR14542",
      "label": "AR 14542",
      "location": "S18E22",
      "mcintosh": "BXO",
      "quality": {
        "level": "fallback",
        "message": "Numbered region is represented, but no accepted live SHARP vector was available; this is not a SHARP magnetic inference."
      },
      "members": {
        "sharpmag": {
          "m1": 1.0,
          "x1": 0.0,
          "source": "Bloomfield et al. (2012) McIntosh-Poisson coverage fallback",
          "quality": "stale-fallback",
          "method": "morphology_fallback",
          "component_id": "AR14542-fallback",
          "issued": "2026-09-24T21:00:00Z",
          "note": "Previous published WXF magnetic probability retained because the current JSOC/SHARP query timed out after three attempts.",
          "valid_start": "2026-09-25T00:00:00+00:00",
          "valid_end": "2026-09-26T00:00:00+00:00"
        }
      },
      "drivers": [
        "McIntosh BXO",
        "No accepted live single-region SHARP vector"
      ]
    }
  ],
  "generation_status": {
    "ok": false,
    "used_previous_forecast": true,
    "previous_issued": "2026-09-24T21:00:00Z",
    "attempts": 3,
    "exit_code": 2,
    "checked_at": "2026-09-25T05:02:53Z",
    "detail": "JSOC/SHARP retrieval failed after three attempts. The prior WXF magnetic probability was retained transparently while all independent forecast sources were refreshed."
  },
  "solar_monitor": {
    "source": "SolarMonitor",
    "source_url": "https://www.solarmonitor.org/forecast.php?date=20260924&region=&indexnum=1",
    "retrieved_at": "2026-09-25T17:14:34Z",
    "table_date": "2026-09-24",
    "valid_start": "2026-09-24T00:00:00Z",
    "valid_end": "2026-09-25T00:00:00Z",
    "wxf_valid_start": "2026-09-25T00:00:00Z",
    "wxf_valid_end": "2026-09-26T00:00:00Z",
    "window_alignment": "latest issue-date comparison; not asserted as an exact WXF target-window match",
    "regional_forecasts": 9,
    "full_disk_method": "maximum regional probability (dominant-region proxy)",
    "note": "Regional MCSTAT/MCEVOL values are reproduced from the latest issue-date SolarMonitor table. SolarMonitor does not publish a full-disk aggregate in this table; the dashboard uses each method's maximum published regional probability to avoid an independence-union inflation. The table's daily window is reported separately from WXF's next-calendar-day window; missing values remain missing."
  },
  "external_sources": {
    "generated_at": "2026-09-25T17:14:34Z",
    "script_version": "1.0.0",
    "sidc_direct": {
      "ok": true,
      "url": "https://www.sidc.be/WMO/FlareForecast.php",
      "issued": "2026-09-25T12:06:43Z",
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
      "ok": true,
      "parser": "3.0.0",
      "info_url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/info?id=SIDC_Operator_FULLDISK",
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=SIDC_Operator_FULLDISK&time.min=2026-09-20T21%3A00%3A00.0&time.max=2026-09-25T21%3A00%3A00.0&format=json&options=fields.all",
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
      "issued": "2026-09-24T12:30:04Z",
      "valid_start": "2026-09-24T12:30:00Z",
      "valid_end": "2026-09-25T12:30:00Z",
      "m1": 31.0,
      "x1": 1.0,
      "selected_record": {
        "start_window": "2026-09-24T12:30:00.0Z",
        "end_window": "2026-09-25T12:30:00.0Z",
        "issue_time": "2026-09-24T12:30:04.0Z",
        "C": "-1",
        "M": "-1",
        "CPlus": 0.91,
        "MPlus": 0.31,
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
        "CPlus_level": 0.91,
        "MPlus_level": 0.31,
        "X_level": 0.01
      }
    },
    "ccmc_metoffice": {
      "dataset_id": "MO_TOT1_FULLDISK",
      "label": "Met Office (MOSWOC)",
      "ok": false,
      "parser": "3.0.0",
      "info_url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/info?id=MO_TOT1_FULLDISK",
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=MO_TOT1_FULLDISK&time.min=2026-09-20T21%3A00%3A00.0&time.max=2026-09-25T21%3A00%3A00.0&format=json&options=fields.all",
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
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=AMOS_v1_FULLDISK&time.min=2026-09-20T21%3A00%3A00.0&time.max=2026-09-25T21%3A00%3A00.0&format=json&options=fields.all",
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
      "issued": "2026-09-25T00:30:00Z",
      "valid_start": "2026-09-25T00:00:00Z",
      "valid_end": "2026-09-26T00:00:00Z",
      "m1": null,
      "x1": 0.12,
      "selected_record": {
        "start_window": "2026-09-25T00:00:00.0Z",
        "end_window": "2026-09-26T00:00:00.0Z",
        "issue_time": "2026-09-25T00:30:00.0Z",
        "C": 0.7733,
        "M": 0.1383,
        "CPlus": "-1",
        "MPlus": "-1",
        "X": 0.0012,
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
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=ASAP_1_FULLDISK&time.min=2026-09-20T21%3A00%3A00.0&time.max=2026-09-25T21%3A00%3A00.0&format=json&options=fields.all",
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
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=ASSA_24H_1_FULLDISK&time.min=2026-09-20T21%3A00%3A00.0&time.max=2026-09-25T21%3A00%3A00.0&format=json&options=fields.all",
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
      "records": 117,
      "issued": "2026-09-25T00:00:00Z",
      "valid_start": "2026-09-25T00:00:00Z",
      "valid_end": "2026-09-26T00:00:00Z",
      "m1": null,
      "x1": 0.0,
      "selected_record": {
        "start_window": "2026-09-25T00:00:00.0Z",
        "end_window": "2026-09-26T00:00:00.0Z",
        "issue_time": "2026-09-25T00:00:00.0Z",
        "C": 0.8631,
        "M": 0.2256,
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
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=ASSA_1_FULLDISK&time.min=2026-09-20T21%3A00%3A00.0&time.max=2026-09-25T21%3A00%3A00.0&format=json&options=fields.all",
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
      "records": 117,
      "issued": "2026-09-25T00:00:00Z",
      "valid_start": "2026-09-25T00:00:00Z",
      "valid_end": "2026-09-25T12:00:00Z",
      "m1": null,
      "x1": 0.0,
      "selected_record": {
        "start_window": "2026-09-25T00:00:00.0Z",
        "end_window": "2026-09-25T12:00:00.0Z",
        "issue_time": "2026-09-25T00:00:00.0Z",
        "C": 0.63,
        "M": 0.12,
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
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=BoM_flare1_FULLDISK&time.min=2026-09-20T21%3A00%3A00.0&time.max=2026-09-25T21%3A00%3A00.0&format=json&options=fields.all",
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
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=MAG4_LOS_FEr_FULLDISK&time.min=2026-09-20T21%3A00%3A00.0&time.max=2026-09-25T21%3A00%3A00.0&format=json&options=fields.all",
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
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=MAG4_LOS_r_FULLDISK&time.min=2026-09-20T21%3A00%3A00.0&time.max=2026-09-25T21%3A00%3A00.0&format=json&options=fields.all",
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
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=MagPy-HMI-LOS_FULLDISK&time.min=2026-09-20T21%3A00%3A00.0&time.max=2026-09-25T21%3A00%3A00.0&format=json&options=fields.all",
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
      "records": 80,
      "issued": "2026-09-25T03:16:01Z",
      "valid_start": "2026-09-25T00:00:00Z",
      "valid_end": "2026-09-26T00:00:00Z",
      "m1": 2.0,
      "x1": 1.0,
      "selected_record": {
        "start_window": "2026-09-25T00:00:00.0Z",
        "end_window": "2026-09-26T00:00:00.0Z",
        "issue_time": "2026-09-25T03:16:01.0Z",
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
    "ccmc_ccmc_magpy": {
      "dataset_id": "MagPy_SHARP_HMI_CEA_FULLDISK",
      "label": "CCMC MagPy SHARP",
      "ok": true,
      "parser": "3.0.0",
      "info_url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/info?id=MagPy_SHARP_HMI_CEA_FULLDISK",
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=MagPy_SHARP_HMI_CEA_FULLDISK&time.min=2026-09-20T21%3A00%3A00.0&time.max=2026-09-25T21%3A00%3A00.0&format=json&options=fields.all",
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
      "records": 90,
      "issued": "2026-09-25T03:02:14Z",
      "valid_start": "2026-09-25T00:00:00Z",
      "valid_end": "2026-09-26T00:00:00Z",
      "m1": 5.0,
      "x1": 4.0,
      "selected_record": {
        "start_window": "2026-09-25T00:00:00.0Z",
        "end_window": "2026-09-26T00:00:00.0Z",
        "issue_time": "2026-09-25T03:02:14.0Z",
        "C": "-1",
        "M": "-1",
        "CPlus": "-1",
        "MPlus": 0.05,
        "X": 0.04,
        "C_uncertainty": "-1",
        "M_uncertainty": "-1",
        "CPlus_uncertainty": "-1",
        "MPlus_uncertainty": 0.024,
        "X_uncertainty": 0.025,
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
      "url": "https://iswa.ccmc.gsfc.nasa.gov/IswaSystemWebApp/flarescoreboard/hapi/data?id=SPS_FULLDISK&time.min=2026-09-20T21%3A00%3A00.0&time.max=2026-09-25T21%3A00%3A00.0&format=json&options=fields.all",
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
      "issued": "2026-09-24T17:00:00Z",
      "valid_start": "2026-09-24T17:00:00Z",
      "valid_end": "2026-09-25T17:00:00Z",
      "m1": null,
      "x1": 1.0,
      "selected_record": {
        "start_window": "2026-09-24T17:00:00.0Z",
        "end_window": "2026-09-25T17:00:00.0Z",
        "issue_time": "2026-09-24T17:00:00.0Z",
        "C": 0.65,
        "M": 0.25,
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
    "swpc": {
      "ok": true,
      "detail": "Official benchmark refreshed independently of SHARP",
      "issued": "2026-09-24T22:00:00+00:00",
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
