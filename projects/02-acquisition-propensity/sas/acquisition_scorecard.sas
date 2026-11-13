/*******************************************************************************
  acquisition_scorecard.sas  |  Maple & Main acquisition project
  Logistic propensity scorecard, the SAS counterpart of the scorecard in
  python/02_train_models.py.

  Input : work/prospect_abt.csv  (written by python/01_build_base.py)
  Output: coefficient table, scored test period, decile lift table, and a
          DATA step that scores new prospects

  Status: written for SAS 9.4 / SAS OnDemand for Academics. It has not been
          executed as part of this build; the Python scorecard is the tested
          equivalent (test AUC 0.68, top-decile lift 2.3x).
*******************************************************************************/

%let project = /home/&sysuserid./analytics-portfolio/projects/02-acquisition-propensity;   /* edit to your path */

proc import datafile="&project./work/prospect_abt.csv" out=work.abt dbms=csv replace;
    guessingrows=5000;
run;

data work.abt;
    set work.abt;
    distance_10km = distance_to_store_km / 10;     /* effect is reported per 10 km */
run;

data work.train work.test;
    set work.abt;
    if role = 'train' then output work.train;
    else output work.test;
run;

/* 1. Fit on prospects first contacted January 2024 to September 2025 ------ */
ods output ParameterEstimates=work.estimates OddsRatios=work.odds_ratios;
proc logistic data=work.train descending namelen=40 outmodel=work.scorecard_model;
    class lead_source(ref='Partner list') age_band(ref='45-54') household_income_band(ref='<50k') / param=ref;
    model converted_flag = lead_source age_band household_income_band
                           web_visits_capped distance_10km has_children email_engaged_flag
          / lackfit;
run;

/* 2. Score the later period ----------------------------------------------- */
proc logistic inmodel=work.scorecard_model;
    score data=work.test out=work.test_scored fitstat;
run;

/* 3. Refresh the baseline: conversion has been rising, so line the average
      predicted rate up with the actual rate in the latest training quarter -- */
proc logistic inmodel=work.scorecard_model;
    score data=work.train(where=(first_contact_date >= '01JUL2025'd)) out=work.recent_scored;
run;

proc sql noprint;
    select log(mean(converted_flag) / (1 - mean(converted_flag))) - log(mean(p_1) / (1 - mean(p_1)))
      into :shift trimmed
    from work.recent_scored;
quit;

data work.test_scored;
    set work.test_scored;
    p_refreshed = 1 / (1 + exp(-(log(p_1 / (1 - p_1)) + &shift.)));   /* approximate intercept update */
run;

/* 4. Decile lift on the test period --------------------------------------- */
proc rank data=work.test_scored out=work.test_ranked groups=10 descending;
    var p_refreshed;
    ranks decile;
run;

proc sql;
    create table work.lift as
    select decile + 1                        as score_decile,
           count(*)                          as prospects,
           sum(converted_flag)               as converters,
           mean(converted_flag)              as conversion_rate format=percent8.1,
           mean(p_refreshed)                 as predicted_rate  format=percent8.1,
           calculated conversion_rate /
             (select mean(converted_flag) from work.test_scored) as lift format=5.2
    from work.test_ranked
    group by decile
    order by decile;
quit;

title "Acquisition scorecard: lift by score decile, October 2025 to September 2026";
proc print data=work.lift noobs; run;
title "Scorecard coefficients and odds ratios";
proc print data=work.estimates noobs; run;
proc print data=work.odds_ratios noobs; run;
title;
