/*******************************************************************************
  weekly_forecast.sas  |  Maple & Main demand forecasting
  Weekly demand forecast with a rolling-origin backtest, the SAS counterpart of
  python/02_backtest.py.

  Input : work/series.csv  (company and category level, from python/01_build_series.py)
  Output: a backtest table of actual against forecast for three methods, and a
          weighted error summary by level and method

  Status: written for SAS 9.4 / SAS OnDemand for Academics. It has not been
          executed as part of this build; the Python version is the tested
          equivalent (2.2% error at company level, 3.7% at category level).
*******************************************************************************/

%let project = /home/&sysuserid./analytics-portfolio/projects/04-demand-forecasting;   /* edit to your path */
%let horizon = 13;     /* weeks ahead to judge */
%let first   = 104;    /* first forecast origin, in weeks from the start */
%let step    = 4;      /* weeks between origins */
%let nor     = 10;     /* number of origins */

proc import datafile="&project./work/series.csv" out=work.series dbms=csv replace;
    guessingrows=5000;
run;

/* Calendar features: trend, five Fourier harmonics, and the trading events a
   planner knows months ahead. Everything here is known before the week starts. */
data work.series;
    set work.series;
    week_of_year = week(week_start, 'v');
    trend = t / 52;
    array s {5} sin1-sin5;
    array c {5} cos1-cos5;
    do k = 1 to 5;
        s{k} = sin(2 * constant('pi') * k * week_of_year / 52.18);
        c{k} = cos(2 * constant('pi') * k * week_of_year / 52.18);
    end;
    peak_holiday   = (47 <= week_of_year <= 52);
    back_to_school = (33 <= week_of_year <= 36);
    log_revenue = log(max(revenue, 1));
    drop k;
run;

proc sort data=work.series; by level series_id t; run;

/* Flyer weeks come from the media plan, which is a separate extract */
proc import datafile="&project./work/calendar.csv" out=work.calendar dbms=csv replace;
    guessingrows=500;
run;

proc sql;
    create table work.model_input as
    select a.*, b.flyer_week
    from work.series a left join work.calendar b on a.t = b.t;
quit;

%macro backtest;
    proc datasets lib=work nolist; delete bt_all; quit;

    %do i = 0 %to %eval(&nor. - 1);
        %let origin = %eval(&first. + &i. * &step.);
        %let last   = %eval(&origin. + &horizon. - 1);

        /* --- benchmark 1: the same week last year --------------------------- */
        proc sql;
            create table work.naive as
            select a.level, a.series_id, a.t, a.revenue as actual,
                   b.revenue as f_naive
            from work.model_input a
            join work.model_input b
              on a.level = b.level and a.series_id = b.series_id and b.t = a.t - 52
            where a.t between &origin. and &last.;
        quit;

        /* --- benchmark 2: last year, reset to the recent level --------------- */
        proc sql;
            create table work.adj as
            select n.*,
                   n.f_naive * (r.recent / max(r.year_ago, 1)) as f_adjusted
            from work.naive n
            join (select level, series_id,
                         mean(case when t between &origin. - 8 and &origin. - 1 then revenue end) as recent,
                         mean(case when t between &origin. - 60 and &origin. - 53 then revenue end) as year_ago
                  from work.model_input group by level, series_id) r
              on n.level = r.level and n.series_id = r.series_id;
        quit;

        /* --- the regression: fitted on everything before the origin ---------- */
        proc glmselect data=work.model_input(where=(t < &origin.)) noprint;
            by level series_id;
            model log_revenue = trend sin1-sin5 cos1-cos5
                                peak_holiday back_to_school flyer_week / selection=none;
            score data=work.model_input(where=(&origin. <= t <= &last.))
                  out=work.scored(rename=(p_log_revenue=log_fit));
        run;

        data work.ridge;
            set work.scored;
            f_ridge = exp(log_fit);
            keep level series_id t f_ridge;
        run;

        proc sql;
            create table work.bt_&i. as
            select a.*, b.f_ridge, &origin. as origin, a.t - &origin. + 1 as horizon
            from work.adj a left join work.ridge b
              on a.level = b.level and a.series_id = b.series_id and a.t = b.t;
        quit;

        proc append base=work.bt_all data=work.bt_&i. force; run;
    %end;
%mend;

%backtest;

/* Weighted absolute percentage error: the retail standard, because it is not
   distorted by weeks where a single series happens to be small.               */
proc sql;
    create table work.summary as
    select level,
           sum(abs(f_naive    - actual)) / sum(actual) as wape_same_week_last_year  format=percent8.1,
           sum(abs(f_adjusted - actual)) / sum(actual) as wape_level_adjusted       format=percent8.1,
           sum(abs(f_ridge    - actual)) / sum(actual) as wape_regression           format=percent8.1,
           count(*) as forecasts
    from work.bt_all
    group by level;
quit;

title "Rolling-origin backtest: weighted absolute percentage error by level";
proc print data=work.summary noobs; run;

proc sql;
    create table work.by_horizon as
    select level, horizon,
           sum(abs(f_adjusted - actual)) / sum(actual) as wape_level_adjusted format=percent8.1,
           sum(abs(f_ridge    - actual)) / sum(actual) as wape_regression     format=percent8.1
    from work.bt_all group by level, horizon;
quit;

title "Error by weeks ahead";
proc print data=work.by_horizon noobs; run;
title;
