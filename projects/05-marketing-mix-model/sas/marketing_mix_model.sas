/*******************************************************************************
  marketing_mix_model.sas  |  Maple & Main marketing mix model
  Adstock, saturation and a constrained mix model in SAS, the counterpart of
  python/02_fit_mmm.py.

  Input : work/mmm_base.csv  (written by python/01_build_base.py)
  Output: fitted model, contribution decomposition and return by channel

  Status: written for SAS 9.4 / SAS OnDemand for Academics. It has not been
          executed as part of this build; the Python version is the tested
          equivalent (R-squared 0.937, out-of-time error 3.5%).
*******************************************************************************/

%let project = /home/&sysuserid./analytics-portfolio/projects/05-marketing-mix-model;   /* edit to your path */

proc import datafile="&project./work/mmm_base.csv" out=work.mmm dbms=csv replace;
    guessingrows=500;
run;

/* The two Display weeks missing from the media extract are interpolated.
   Reading them as zero would invent a natural experiment that never happened. */
proc expand data=work.mmm out=work.mmm_filled method=join;
    id t;
    convert display = display_filled / observed=average;
run;

data work.mmm;
    merge work.mmm work.mmm_filled(keep=t display_filled);
    by t;
    if display = 0 then display = display_filled;
    trend = t / 52;
    array s {3} sin1-sin3;
    array c {3} cos1-cos3;
    do k = 1 to 3;
        s{k} = sin(2 * constant('pi') * k * week_of_year / 52.18);
        c{k} = cos(2 * constant('pi') * k * week_of_year / 52.18);
    end;
    log_revenue = log(revenue);
    drop k display_filled;
run;

/* ---------------------------------------------------------------------------
   Adstock: this week's pressure plus a share of last week's. The decay values
   below come from the search in the Python build; re-run that search if the
   media plan changes shape.
   ------------------------------------------------------------------------- */
%let decay_tv = 0.7;  %let decay_ps = 0.0;  %let decay_pso = 0.7;
%let decay_di = 0.8;  %let decay_fl = 0.0;  %let decay_em = 0.0;

data work.adstocked;
    set work.mmm;
    retain a_tv a_ps a_pso a_di a_fl a_em 0;
    a_tv  = tv          + &decay_tv.  * lag(a_tv);
    a_ps  = paid_search + &decay_ps.  * lag(a_ps);
    a_pso = paid_social + &decay_pso. * lag(a_pso);
    a_di  = display     + &decay_di.  * lag(a_di);
    a_fl  = flyer       + &decay_fl.  * lag(a_fl);
    a_em  = email       + &decay_em.  * lag(a_em);
    if _n_ = 1 then do;
        a_tv = tv; a_ps = paid_search; a_pso = paid_social;
        a_di = display; a_fl = flyer; a_em = email;
    end;
run;

/* Saturation: half the maximum effect at the half-saturation point ---------- */
proc sql noprint;
    select mean(a_tv), mean(a_ps), mean(a_pso), mean(a_di), mean(a_fl), mean(a_em)
      into :m_tv, :m_ps, :m_pso, :m_di, :m_fl, :m_em
    from work.adstocked;
quit;

%macro hill(var, mean, shape, mult);
    s_&var. = (&var.**&shape.) / (&var.**&shape. + (&mult. * &mean.)**&shape.);
%mend;

data work.model_input;
    set work.adstocked;
    %hill(a_tv,  &m_tv.,  2.0, 2.3)
    %hill(a_ps,  &m_ps.,  2.0, 1.7)
    %hill(a_pso, &m_pso., 1.7, 1.0)
    %hill(a_di,  &m_di.,  2.0, 0.4)
    %hill(a_fl,  &m_fl.,  1.7, 0.6)
    %hill(a_em,  &m_em.,  2.0, 0.8)
run;

/* ---------------------------------------------------------------------------
   Sales = base x (1 + sum of channel lifts).

   PROC NLIN fits the two halves together and holds every channel coefficient
   at or above zero, because media cannot sell less than nothing.
   ------------------------------------------------------------------------- */
proc nlin data=work.model_input method=marquardt maxiter=500 converge=1e-8;
    parms a0=14.5 b_trend=0.05 b_sin1=0 b_cos1=0 b_sin2=0 b_cos2=0 b_sin3=0 b_cos3=0
          b_peak=0.1 b_bts=0.02 b_price=0
          beta_tv=0.05 beta_ps=0.05 beta_pso=0.03 beta_di=0.01 beta_fl=0.04 beta_em=0.02;
    bounds beta_tv >= 0, beta_ps >= 0, beta_pso >= 0,
           beta_di >= 0, beta_fl >= 0, beta_em >= 0;

    base = exp(a0 + b_trend*trend + b_sin1*sin1 + b_cos1*cos1 + b_sin2*sin2 + b_cos2*cos2
               + b_sin3*sin3 + b_cos3*cos3 + b_peak*peak_holiday + b_bts*back_to_school
               + b_price*price_index);
    lift = beta_tv*s_a_tv + beta_ps*s_a_ps + beta_pso*s_a_pso
         + beta_di*s_a_di + beta_fl*s_a_fl + beta_em*s_a_em;

    model revenue = base * (1 + lift);
    output out=work.fitted predicted=fit;
    ods output ParameterEstimates=work.estimates;
run;

/* Contribution by channel: base x that channel's lift, week by week --------- */
proc sql noprint;
    select estimate into :p_tv, :p_ps, :p_pso, :p_di, :p_fl, :p_em
    from work.estimates where parameter like 'beta_%' order by parameter;
quit;

data work.decomposition;
    merge work.model_input work.fitted(keep=fit);
    base = fit / (1 + &p_tv.*s_a_tv + &p_ps.*s_a_ps + &p_pso.*s_a_pso
                    + &p_di.*s_a_di + &p_fl.*s_a_fl + &p_em.*s_a_em);
    c_tv  = base * &p_tv.  * s_a_tv;
    c_ps  = base * &p_ps.  * s_a_ps;
    c_pso = base * &p_pso. * s_a_pso;
    c_di  = base * &p_di.  * s_a_di;
    c_fl  = base * &p_fl.  * s_a_fl;
    c_em  = base * &p_em.  * s_a_em;
run;

proc sql;
    create table work.roi as
    select 'TV'          as channel length=12, sum(c_tv)  as contribution, sum(tv)          as spend,
           calculated contribution / calculated spend as roi format=8.2 from work.decomposition
    union all select 'Paid Search', sum(c_ps),  sum(paid_search), sum(c_ps)/sum(paid_search)  from work.decomposition
    union all select 'Paid Social', sum(c_pso), sum(paid_social), sum(c_pso)/sum(paid_social) from work.decomposition
    union all select 'Display',     sum(c_di),  sum(display),     sum(c_di)/sum(display)      from work.decomposition
    union all select 'Flyer',       sum(c_fl),  sum(flyer),       sum(c_fl)/sum(flyer)        from work.decomposition
    union all select 'Email',       sum(c_em),  sum(email),       sum(c_em)/sum(email)        from work.decomposition;
quit;

title "Contribution and return by channel";
proc print data=work.roi noobs; run;

/* -----------------------------------------------------------------------------
   IMPORTANT. Run this model from several starting points before reporting it.
   Change the parms line above and refit: the fit statistic barely moves while
   total media contribution can more than double. That spread is the honest
   uncertainty, and only an in-market test can narrow it.
   -------------------------------------------------------------------------- */
title;
