# openrails-tools
Simple tools and scripts to manage OpenRails content.
Created for my own use, and made available (without any guarantees) here.

### Summary

- **ORTS-CopyTrains.py**
  Copy the trains required by a route from another content folder.

- **ORTS-ShowRollingStockFile.py**
  Show an engine or wagon file in UTF-8, with all includes expanded.

-  **ORTS-RollingStockScanner.py**
   Find engines and wagons, and list important attributes in CSV format.

### ORTS-CopyTrains.py
Python script to copy the trains required by a route from another content folder.
Scans the route's services for consists used.
Copies the consists from the specified content folder to the route's trains folder
(actually the content folder where the route is).
Then scans the consist file for engines and wagons, and for each one
copies the whole trainset sub-folder.

Useful, in conjunction with `Default-Content-Installer.exe`, to extract a route
in a shared content folder into a separate content folder.

```
>py ORTS-CopyTrains.py -h
usage: ORTS-CopyTrains.py [-h] [-v] routePath contentPath

Copy all the consists and rolling stock (trainset) needed by a route from another content folder.

positional arguments:
  routePath      Route folder, to copy the trains to. The folder that contains the Services sub-folder.
  contentPath    Content folder, to copy the trains from. The folder that contains the Trains sub-folder

options:
  -h, --help     show this help message and exit
  -v, --verbose
```

Example:
```
>py ORTS-CopyTrains.py c:\Games\OpenRails\Content\MariasPass-3.1-MSTS\routes\Marias31 c:\Games\OpenRails\Content\PrevMSTS
Info: copying trains (consists, trainset folders) for route "c:\Games\OpenRails\Content\MariasPass-3.1-MSTS\routes\Marias31" from content folder "c:\Games\OpenRails\Content\PrevMSTS".
Sum: copied 34 Consists and 28 Trainsets folders.
```

### ORTS-ShowRollingStockFile.py
Python script to show an engine or wagon file. 
Includes are expanded to create a complete file.
The output is in UTF-8 - OpenRails accepts UTF-8 files (MSTS uses UTF-16).

```
>py ORTS-ShowRollingStockFile.py -h
usage: ORTS-ShowRollingStockFile.py [-h] filePath
positional arguments:
  filePath    File (eng or wag) to list.
options:
  -h, --help  show this help message and exit
```

Example:
```
py ORTS-ShowRollingStockFile.py "BNSF_GP38_2264.eng" > BNSF_GP38_new.eng
641 lines in expanded file  BNSF_GP38_2264.eng
```

### ORTS-RollingStockScanner.py
Python script to list all the engines and wagons in (or below) the specified directory.
For each engine or wagon, a set of (physics centric) attributes are output in CSV format.

```
>py ORTS-RollingStockScanner.py -h
usage: ORTS-RollingStockScanner.py [-h] [-f FILTER] [-v] dirPath
positional arguments:
  dirPath              Directory where to search for eng and wag files.
options:
  -h, --help           show this help message and exit
  -f, --filter FILTER  Optional filter. "eng" limits to engines, "wag" limits to wagons, any other value is matched to the file name
  -v, --verbose
```

Example:
```
>py ORTS-RollingStockScanner.py -f dash9 c:\Games\OpenRails\Content > c:\Games\OpenRails\Content\ContentList.csv
Processed 1 Eng and 0 Wag files, total 1; generated 0 warnings
```

Output generated (CSV file):
```
Package,Directory,File,Name,Type,SubType,MaxSpeed,MaxPower,MaxForce,MaxBrakeForce,Weight,Length,Wheels/Axles,CouplerStrength,Friction,Adhesion,DerailRailForce,DerailBufferForce,TotalLength
PrevMSTS,DASH9,dash9.eng,Dash9,Engine,Diesel,74mph,3267kW,634.7kN,94.6kN,187t,21.8m,12 | 4,5e7N,1976N/m/s | 0 | 0.7mph | 20.85N/m/s | 1.8,0.32 | 0.62 | 1.8,2.5*187t,515kN,_
```
