#!/usr/bin/env python3
"""Read two fixed, public-facing provider scripts; never execute their contents."""
import json
import collect_products as c
host = 'a-effort-astro-noa-gr.content.swe.s2p.esa.int'
c.access.AUTH_HOSTS[host] = 'swe_contentproxy'
base = 'https://' + host + '/prod/web/js/'
c.save('aeffort-main', base + 'main.js', None)
c.save('aeffort-functions', base + 'functions.js', None)
(c.ROOT / 'manifest-followup.json').write_text(json.dumps(c.report, indent=2))
print(json.dumps({'products': c.report['requests']}, indent=2))
