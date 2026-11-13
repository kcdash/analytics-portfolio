/*******************************************************************************
  persona_segmentation.sas  |  Maple & Main segmentation project
  Needs-based personas in SAS: cluster on category mix, then label a customer
  only when the evidence supports it.

  Input : work/seg_features.csv  (written by python/01_build_features.py)
  Output: cluster centres, a scored customer table, and the share of customers
          confident enough to carry a label

  Status: written for SAS 9.4 / SAS OnDemand for Academics. It has not been
          executed as part of this build; the Python version is the tested
          equivalent (five personas, 19% of customers labelled, 75% purity
          against the latent shopper types).
*******************************************************************************/

%let project  = /home/&sysuserid./analytics-portfolio/projects/03-segmentation-personas;  /* edit to your path */
%let k        = 5;      /* personas */
%let shrink   = 20;     /* items of shrinkage toward the average shopper */
%let minlodds = 2;      /* a label needs the leader to beat the runner-up by exp(2) ~ 7 times */

proc import datafile="&project./work/seg_features.csv" out=work.feat dbms=csv replace;
    guessingrows=5000;
run;

/* 1. Average category mix across the whole base -------------------------- */
proc sql noprint;
    select sum(u_apparel), sum(u_home), sum(u_outdoor), sum(u_electronics),
           sum(u_beauty), sum(u_grocery), sum(u_toys), sum(u_sports), sum(units_total)
      into :b1, :b2, :b3, :b4, :b5, :b6, :b7, :b8, :btot
    from work.feat;
quit;

%macro base;
    %do i = 1 %to 8; base&i. = &&b&i.. / &btot.; %end;
%mend;

/* 2. Shrunk category shares: a small basket is pulled back to the average - */
data work.shares;
    set work.feat;
    %base;
    array u {8} u_apparel u_home u_outdoor u_electronics u_beauty u_grocery u_toys u_sports;
    array b {8} base1-base8;
    array s {8} s1-s8;
    do i = 1 to 8;
        s{i} = (u{i} + &shrink. * b{i}) / (units_total + &shrink.);
    end;
    drop i;
run;

/* 3. Cluster on the shrunk shares ---------------------------------------- */
proc standard data=work.shares out=work.shares_std mean=0 std=1;
    var s1-s8;
run;

proc fastclus data=work.shares_std out=work.clustered outstat=work.clusstat
              maxclusters=&k. maxiter=100 converge=0 random=42;
    var s1-s8;
run;

/* Cluster centres back on the original scale, normalised to add to one ---- */
proc means data=work.clustered noprint;
    class cluster;
    var s1-s8;
    output out=work.centres(where=(_type_=1)) mean=c1-c8;
run;

data work.centres;
    set work.centres;
    array c {8} c1-c8;
    total = sum(of c{*});
    do i = 1 to 8; c{i} = c{i} / total; end;
    drop i total _type_ _freq_;
run;

proc transpose data=work.centres out=work.centres_long prefix=val;
    by cluster;
    var c1-c8;
run;

/* 4. Label each customer by multinomial likelihood ------------------------
      The score for a persona is sum(units in a category x log(share for that
      persona)). The average shopper is scored the same way and competes as an
      extra option, so an ordinary basket wins no label.                     */
proc sql noprint;
    select count(*) into :ncl from work.centres;
quit;

data work.scored;
    if _n_ = 1 then do;
        declare hash h(dataset: "work.centres_long");
        h.definekey("cluster", "_name_");
        h.definedata("val1");
        h.definedone();
    end;
    set work.shares;
    array u {8} u_apparel u_home u_outdoor u_electronics u_beauty u_grocery u_toys u_sports;
    array b {8} base1-base8;
    array ll {&ncl.} _temporary_;
    length persona $20;

    /* the average shopper, as the option to beat */
    ll_base = 0;
    do i = 1 to 8;
        if u{i} > 0 then ll_base + u{i} * log(b{i});
    end;

    best = .; best_ll = ll_base; second_ll = .;
    do cl = 1 to &ncl.;
        score = 0;
        do i = 1 to 8;
            _name_ = cats("c", put(i, 1.));
            cluster = cl;
            if h.find() = 0 and u{i} > 0 then score + u{i} * log(max(val1, 1e-4));
        end;
        ll{cl} = score;
    end;

    /* best and runner-up across the personas and the average shopper */
    best_ll = ll_base; best = 0;
    do cl = 1 to &ncl.;
        if ll{cl} > best_ll then do; second_ll = best_ll; best_ll = ll{cl}; best = cl; end;
        else if second_ll = . or ll{cl} > second_ll then second_ll = ll{cl};
    end;
    margin = best_ll - second_ll;

    if best > 0 and margin >= &minlodds. then persona = cats("Persona ", put(best, 1.));
    else persona = "No clear persona";
    keep customer_id units_total spend_365d margin persona;
run;

proc freq data=work.scored;
    tables persona / nocum;
    title "Share of customers carrying a persona";
run;

proc means data=work.scored n mean median;
    class persona;
    var units_total spend_365d margin;
    title "Labelled customers buy more, which is why they can be labelled";
run;
title;
