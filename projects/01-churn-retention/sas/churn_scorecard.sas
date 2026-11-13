/*******************************************************************************
  churn_scorecard.sas  |  Maple & Main churn project
  Logistic churn scorecard, the SAS counterpart of the logistic benchmark in
  python/02_train_churn_model.py.

  Input : work/churn_abt.csv  (written by python/01_build_features.py)
  Output: scored test snapshot, decile lift table, KS statistic, score stability

  Status: written for SAS 9.4 / SAS OnDemand for Academics. It has not been
          executed as part of this build; the Python logistic model is the
          tested equivalent (test AUC 0.81, top-decile lift 3.3x).
*******************************************************************************/

%let project = /home/&sysuserid./analytics-portfolio/projects/01-churn-retention;   /* edit to your path */

/* 1. Read the analytical base table --------------------------------------- */
proc import datafile="&project./work/churn_abt.csv" out=work.abt dbms=csv replace;
    guessingrows=5000;
run;

/* 2. Missing values: flag, then fill with the training median ------------- */
%let fillvars = avg_basket_365d discount_share_365d promo_line_share_365d avg_categories_per_order
                digital_order_share_365d avg_gap_days overdue_ratio min_csat_180d;

data work.abt;
    set work.abt;
    miss_gap  = missing(avg_gap_days);      /* only one order in the last year  */
    miss_csat = missing(min_csat_180d);     /* no satisfaction survey answered  */
run;

proc stdize data=work.abt(where=(role='train')) out=work._train_filled
            outstat=work.medians method=median reponly;
    var &fillvars.;
run;

proc stdize data=work.abt out=work.abt_filled method=in(work.medians) reponly;
    var &fillvars.;
run;

data work.train work.validate work.test;
    set work.abt_filled;
    if role = 'train' then output work.train;
    else if role = 'validate' then output work.validate;
    else output work.test;
run;

/* 3. Fit on four training snapshots, score the out-of-time test snapshot -- */
%let numvars = tenure_days email_opt_in sms_opt_in recency_days orders_90d orders_prev_90d orders_365d
               spend_365d spend_90d avg_basket_365d discount_share_365d promo_line_share_365d
               avg_categories_per_order digital_order_share_365d redemptions_365d avg_gap_days overdue_ratio
               web_sessions_1m web_sessions_3m web_sessions_prev_3m abandoned_carts_3m
               service_contacts_90d service_contacts_365d complaints_180d unresolved_180d min_csat_180d
               crm_contacts_365d crm_opens_365d crm_clicks_365d miss_gap miss_csat;

ods output ParameterEstimates=work.estimates Association=work.train_assoc;
proc logistic data=work.train descending namelen=40;
    class province age_band loyalty_tier(ref='Bronze') acquisition_channel(ref='Store') / param=ref;
    model churn_180d = &numvars. province age_band loyalty_tier acquisition_channel
          / selection=none lackfit;
    score data=work.validate out=work.validate_scored;
    score data=work.test     out=work.test_scored fitstat;
run;

/* 4. Decile lift on the test snapshot ------------------------------------- */
proc rank data=work.test_scored out=work.test_ranked groups=10 descending;
    var p_1;
    ranks decile;
run;

proc sql;
    create table work.lift as
    select decile + 1                               as risk_decile,
           count(*)                                 as customers,
           sum(churn_180d)                          as churners,
           mean(churn_180d)                         as churn_rate format=percent8.1,
           calculated churn_rate /
             (select mean(churn_180d) from work.test_scored) as lift format=5.2
    from work.test_ranked
    group by decile
    order by decile;
quit;

title "Churn scorecard: lift by risk decile, May 2026 test snapshot";
proc print data=work.lift noobs; run;

/* 5. Separation (KS) and score stability between validation and test ------ */
proc npar1way data=work.test_scored edf noprint;
    class churn_180d;
    var p_1;
    output out=work.ks(keep=_d_ rename=(_d_=ks_statistic)) edf;
run;

data work.both;
    set work.validate_scored(in=v) work.test_scored;
    length sample $8;
    sample = ifc(v, 'validate', 'test');
run;

proc rank data=work.both out=work.both_ranked groups=10;
    var p_1;
    ranks band;
run;

proc sql;
    create table work.psi as
    select sum((t_share - v_share) * log(t_share / v_share)) as psi format=8.4
    from (select band,
                 sum(sample = 'test')     / (select count(*) from work.both where sample = 'test')     as t_share,
                 sum(sample = 'validate') / (select count(*) from work.both where sample = 'validate') as v_share
          from work.both_ranked
          group by band);
quit;

title "Separation (KS) and population stability index";
proc print data=work.ks noobs; run;
proc print data=work.psi noobs; run;
title;
