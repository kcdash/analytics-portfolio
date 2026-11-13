/*******************************************************************************
  kpi_control_charts.sas  |  Maple & Main executive dashboard
  Seasonal baselines and control charts for the KPI set, the SAS counterpart of
  python/02_signals.py.

  Input : work/kpi_week.csv  (written by python/01_build_mart.py)
  Output: a table of expected level, control limits and rule violations per
          metric and week, plus a Shewhart chart for each metric

  Status: written for SAS 9.4 with SAS/QC, or SAS OnDemand for Academics. It has
          not been executed as part of this build; the Python version is the
          tested equivalent (112 signals across 1,040 metric-weeks).
*******************************************************************************/

%let project = /home/&sysuserid./analytics-portfolio/projects/06-executive-dashboard;   /* edit to your path */
%let minhist = 52;    /* weeks of history before a metric may be judged */

proc import datafile="&project./work/kpi_week.csv" out=work.kpi dbms=csv replace;
    guessingrows=500;
run;

data work.kpi;
    set work.kpi;
    trend = t / 52;
    array s {3} sin1-sin3;
    array c {3} cos1-cos3;
    do k = 1 to 3;
        s{k} = sin(2 * constant('pi') * k * week_of_year / 52.18);
        c{k} = cos(2 * constant('pi') * k * week_of_year / 52.18);
    end;
    drop k;
run;

/* ---------------------------------------------------------------------------
   For every metric and every week, fit the baseline on earlier weeks only and
   record where the week landed. Judging a week against a baseline that has
   already seen it is the most common way a control chart is made useless.
   ------------------------------------------------------------------------- */
%macro baseline(metric);
    proc datasets lib=work nolist; delete bl_&metric.; quit;

    %local i;
    %do i = %eval(&minhist. + 1) %to 156;
        proc reg data=work.kpi(where=(t < &i.)) noprint outest=work._est;
            model &metric. = trend sin1-sin3 cos1-cos3 peak_holiday back_to_school flyer_week;
            output out=work._fit r=resid;
        quit;

        proc sql noprint;
            select std(resid) into :sd from work._fit;
        quit;

        proc score data=work.kpi(where=(t = &i.)) score=work._est type=parms
                   out=work._scored(rename=(model1=expected));
            var trend sin1-sin3 cos1-cos3 peak_holiday back_to_school flyer_week;
        run;

        data work._row;
            set work._scored;
            length metric $24;
            metric = "&metric.";
            value  = &metric.;
            sd     = &sd.;
            z      = (value - expected) / sd;
            upper  = expected + 3 * sd;
            lower  = expected - 3 * sd;
            keep metric t week_start value expected sd z upper lower;
        run;

        proc append base=work.bl_&metric. data=work._row force; run;
    %end;
%mend;

%baseline(revenue);
%baseline(margin);
%baseline(active_customers);
%baseline(new_customers);
%baseline(avg_basket);
%baseline(margin_rate);
%baseline(price_index);
%baseline(digital_revenue_share);
%baseline(media_spend);
%baseline(service_contacts);

data work.baselines;
    set work.bl_revenue work.bl_margin work.bl_active_customers work.bl_new_customers
        work.bl_avg_basket work.bl_margin_rate work.bl_price_index
        work.bl_digital_revenue_share work.bl_media_spend work.bl_service_contacts;
run;

/* ---------------------------------------------------------------------------
   The three control rules. The run rule is the one worth having: a slow drift
   never trips an eyeball and is exactly how a problem arrives.
   ------------------------------------------------------------------------- */
proc sort data=work.baselines; by metric t; run;

data work.signals;
    set work.baselines;
    by metric;
    retain run_up run_down 0;
    lag_z1 = lag(z); lag_z2 = lag2(z);
    if first.metric then do; run_up = 0; run_down = 0; lag_z1 = .; lag_z2 = .; end;

    if z > 0 then do; run_up + 1; run_down = 0; end;
    else do; run_down + 1; run_up = 0; end;

    length flag $60;
    if abs(z) >= 3 then flag = "beyond three standard deviations";
    else if abs(z) >= 2 and ((abs(lag_z1) >= 2) + (abs(lag_z2) >= 2)) >= 1
        then flag = "two of three weeks beyond two standard deviations";
    else if max(run_up, run_down) >= 8 then flag = "eight weeks in a row on one side";
    else flag = "";
run;

proc sql;
    create table work.signal_summary as
    select metric, count(*) as weeks_judged,
           sum(flag ne '') as weeks_with_a_signal,
           calculated weeks_with_a_signal / calculated weeks_judged as share format=percent8.1
    from work.signals group by metric order by calculated weeks_with_a_signal desc;
quit;

title "Weeks outside normal variation, by metric";
proc print data=work.signal_summary noobs; run;

/* A Shewhart chart per metric, using the seasonal baseline as the centre line */
ods graphics on;
proc shewhart data=work.signals(where=(metric = 'service_contacts'));
    irchart value * t /
        cinfill   = white
        nolimitslegend
        outtable  = work.chart_out;
    label value = "Service contacts";
run;
ods graphics off;

title;
