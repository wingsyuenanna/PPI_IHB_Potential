[![DOI](https://zenodo.org/badge/doi/10.5281/zenodo.4687185.svg)](https://doi.org/10.5281/zenodo.4687185)

﻿# generic typical day hourly profiles dependent on day-type and country for heat demand in the non-metallic minerals industry




## Repository structure

Files:
```
readme.md               -- Readme file 
datapackage.json        -- Includes the meta information of the dataset for processing and data integration
data/hotmaps_task_2.7_load_profile_industry_non_metalic_minerals_generic.csv  -- contains the dataset in CSV format
```

## Documentation


This dataset provides the hourly heat demand in the non-metallic minerals industry for typical days. In this context we emphasize, that profiles are not measured but modelled taking into consideration factors amongst others shift work patterns, historical output per month/weekday. 
The profiles can be used to assemble a yearlong demand profile for a NUTS2 region, if the structure of the days in a year (i.e. sequence of weekdays, Saturdays and Sundays/Holidays) for the specific region and year is available. 

Create your own profile:

Generic files are supposed to enable the user to produce load profiles of his own using own data and a structure year of her/his own choice. 
For the industrial load profiles, we provided a yearlong profile for the year 2018 (in which the typedays are set in the order of this year). However, we want to give the user the opportunity to use a structure year of his/her choice.
Structure year in this context means the order of days in the course of the year. The columns “day type” refers to the type of a day in the week:
- weekdays = typeday 0;
- saturday or day before a holiday = typeday 1;
- sunday or holiday = typeday 2
The column “month” refers to the month of the year. 1 = January, 2 = February etc.
Yearlong profiles can be generated from the generic profiles provided here following the following steps:
- determining the structure year for which the profiles are generated
- ordering the typedays for each month according to the selected year
- allocating the respective load value for the typeday/month tuple to each hour
- scaling the total sum of the annual yearlong profile (i.e. the integral of the profile) according to the annual total demand

For detailed explanations and a graphical illustration of the dataset please see the [Hotmaps WP2 report](https://www.hotmaps-project.eu/wp-content/uploads/2018/03/D2.3-Hotmaps_for-upload_revised-final_.pdf) section 2.8 page 121ff.


## Limitations of the datasets

The datasets provided have to be interpreted as simplified indicator to enable the analysis that can be carried out within the Hotmaps toolbox. It should be noted that the results of the toolbox can be improved with recorded heat demand data of local representatives of the non-metalic minerals industry.


## References
[1] [TrustEE - Report on current status of Process heat in Europe: sectors, processes, geographical distribution, system layouts and energy sources](https://www.trust-ee.eu/files/otherfiles/0000/0008/TrustEE_D1_1.pdf) AEE Intec, Fraunhofer ISE, Reen AG, Universidade de Evora, 2016.

[2] [Comparative Analysis of Operating Hours and Working Times in the European Union] Delson, Bauer, Cette, Smith, 2009,Heidelberg: Physica-Verlag.

[3] [Employment at atypical working time as percentage of the total employment, by European socio-economic group](http://appsso.eurostat.ec.europa.eu/nui/show.do?dataset=lfsa_esegatyp&lang=en) Eurostat, 2018, checked on 29.01.18.

[4] [Bevoelkerung und Erwebstaetigkeit. Erwerbsbeteiligung der Bevoelkerung Ergebnisse des Mikrozensus zum Arbeitsmarkt.](https://www.destatis.de/DE/Publikationen/Thematisch/Arbeitsmarkt/Erwerbstaetige/ErwerbsbeteiligungBevoelkung2010410167004.pdf?__blob=publicationFile) Federal Statistical Office Germany, 2016, Fachserie 1 Reihe 4.1, checked on 30.01.18.


## How to cite


Simon Pezzutto, Stefano Zambotti, Silvia Croce, Pietro Zambelli, Giulia Garegnani, Chiara Scaramuzzino, Ramón Pascual Pascuas, Alyona Zubaryeva, Franziska Haas, Dagmar Exner (EURAC), Andreas Müller (e‐think), Michael Hartner (TUW), Tobias Fleiter, Anna‐Lena Klingler, Matthias Kühnbach, Pia Manz, Simon Marwitz, Matthias Rehfeldt, Jan Steinbach, Eftim Popovski (Fraunhofer ISI) Reviewed by Lukas Kranzl, Sara Fritz (TUW)
Hotmaps Project, D2.3 WP2 Report – Open Data Set for the EU28, 2018 [www.hotmaps-project.eu](https://www.hotmaps-project.eu/wp-content/uploads/2018/03/D2.3-Hotmaps_for-upload_revised-final_.pdf) 


## Authors

Matthias Kuehnbach, Simon Marwitz, Anna-Lena Klingler <sup>*</sup>,

<sup>*</sup> [Fraunhofer ISI](https://isi.fraunhofer.de/)
Fraunhofer ISI, Breslauer Str. 48, 
76139 Karlsruhe


## License


Copyright © 2016-2018: Matthias Kuehnbach, Anna-Lena Klingler, Simon Marwitz

Creative Commons Attribution 4.0 International License

This work is licensed under a Creative Commons CC BY 4.0 International License.


SPDX-License-Identifier: CC-BY-4.0

License-Text: https://spdx.org/licenses/CC-BY-4.0.html


## Acknowledgement

We would like to convey our deepest appreciation to the Horizon 2020 [Hotmaps Project](http://www.hotmaps-project.eu/) (Grant Agreement number 723677), which provided the funding to carry out the present investigation.
