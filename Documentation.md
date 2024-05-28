# Documentation

## Naming of Kadi records  

Each record starts with 'GUF IfG EPMA'

## Entries in Kadi records  

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
:orange_circle: This file (in rare cases) could be missing, so it might be sensible to test for its availability and not if it is not available.

Image files as .jpg, .tif, .bmp  

**To be considered**  
A single mesurement campaign can use different quantitative measurement programs. The results of these are then spread across multiple Kadi entries, using the labelling '-a', '-b', ... after the Kadi record name.
