import re
import urllib.request

js = urllib.request.urlopen("http://www.pwmat.com/js/app.712bc0e7.js", timeout=30).read().decode("utf-8", "replace")
m = re.search(r'\$e=\[(\{id:\d+,name:"[^"]+",summary:"[^"]*"\},?)+\]', js)
if m:
    print(m.group(0)[:3000])
else:
    for m2 in re.finditer(r'name:"(NCPP[^"]+\.zip|ONCV[^"]+\.zip|H\.zip|GTH[^"]+\.zip|BASIS[^"]+\.zip)"', js):
        print(m2.group(1))
