# Documentation

## App Link  

https://epma-data-tools.streamlit.app

## Naming of Kadi records  

Each record starts with 'GUF IfG EPMA'  
A single measurement session, i.e., the session of one party with a single set of samples can make use of different measurement programs, i.e., different measurement setups and parameters. For example, when first silicates and then sulphides are measured. In this case, the results have all the same name, but for each specific measurement program a separate record is created, with a lettered postfix in the form of: -a, -b, -c, ... The first record with the postfix -a contains files that are similar for all records with this name, e.g., overview images.  
Records of a single measurement session might be all put in a Kadi Collection.

## Entries in Kadi records  


### Types of Kadi records
There are 3 different categories: quantitative, element maps, qualitative. Each category requires its specific measurement setup. Therefore, each category requires is separate Kadi record.

### Quantitative Analyses  

**Must contain**  

*summary{date}.csv*  
The output from: summary, all, to excel, save as .csv  
  
*normal.txt*  
The output from: summary, normal, type out  
  
*summary standard.txt*  
The output from: summary, standard, type out  

*quick standard.txt*  
The output from: quick menu, right click recipe, ??  

  
**Can contain**  

*standard measurements.xlsx*  
File with the results from the standard measurements, with colour results, therefore an excel file  
-> This file can (in rare cases) be missing, so it might be sensible to test for its availability and not if it is not available.

Image files as .jpg, .tif, .bmp  


### Map Analyses  

**Must contain**  

*quick standard.txt*  
The output from: quick menu, right click recipe, ??  

*{map file}.csv*  
The naming of {map file} is as follows:  
map {nr} {Eds}{internal designation} {element name} {measured charactersistic line}.csv  
e.g.:  
map 2 data004 Mg Ka.csv  
note that 'Eds' only occurs when the element was measured with EDS, when 'Eds' is missing, the element was measured with WDS
  
**Can contain**  

1 or 2 more map files labelled "data{nr} COMPO.csv" or "data{nr} SE.csv", which are maps of BSE- and/or SE-signals, i.e., essentially BSE- and SE-images.
Image files as .jpg, .tif, .bmp  


### Qualitative Analyses  

**Must contain**  

*summary{date}.csv*  
The output from: summary, all, to excel, save as .csv  
  
*normal.txt*  
The output from: summary, normal, type out  
  
*summary standard.txt*  
The output from: summary, standard, type out  

*quick standard.txt*  
The output from: quick menu, right click recipe, ??  
