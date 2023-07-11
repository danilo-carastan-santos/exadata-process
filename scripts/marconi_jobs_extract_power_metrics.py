import argparse
import sys
import pandas as pd
import numpy as np
from scipy.stats import iqr

"""
Read input data
"""
def read_data(rootdir):
    df_jobs_single = pd.read_csv(rootdir+"/plugin=job_table/metric=job_info_marconi100/a_0_filter123_singlenode.csv")
    df_jobs_multi = pd.read_csv(rootdir+"/plugin=job_table/metric=job_info_marconi100/a_0_filter123_multinode.csv")
    df_power_single = pd.read_csv(rootdir+"/plugin=ipmi_pub/metric=total_power/a_0_filter123_singlenode.csv")
    df_power_multi = pd.read_csv(rootdir+"/plugin=ipmi_pub/metric=total_power/a_0_filter123_multinode.csv")
    df_jobs = pd.concat([df_jobs_single, df_jobs_multi]).reset_index(drop=True)
    df_power = pd.concat([df_power_single, df_power_multi]).reset_index(drop=True)
    df_power['node'] = pd.to_numeric(df_power['node'])
    df_power['value'] = pd.to_numeric(df_power['value'])
    return df_jobs, df_power


"""
Calculate jobs' power aggregation metrics
"""
def calculate_agg_metrics(df_jobs, df_power):
    powertrace_jobs = [df_power[df_power["job_id"]==x]['value'].values for x in df_jobs['job_id'].values]
    df_jobs["total_power_max_watts"] = [x.max() for x in powertrace_jobs]
    df_jobs["total_power_mean_watts"] = [x.mean() for x in powertrace_jobs]
    df_jobs["total_power_median_watts"] = [np.median(x) for x in powertrace_jobs]
    df_jobs["total_power_std_watts"] = [x.std() for x in powertrace_jobs]
    df_jobs["total_power_iqr_watts"] = [iqr(x, rng=(25, 75)) for x in powertrace_jobs]
    df_jobs["total_power_1090range_watts"] = [iqr(x, rng=(10, 90)) for x in powertrace_jobs]
    return df_jobs


"""
Save results
"""
def save_results(df_jobs_aggmetrics, rootdir):
    df_jobs_aggmetrics.to_csv(rootdir+"/plugin=job_table/metric=job_info_marconi100/a_0_filter123_aggmetrics.csv")

"""
Run workflow
"""
def run_workflow(rootdir):
    df_jobs, df_power = read_data(rootdir)
    df_jobs_aggmetrics = calculate_agg_metrics(df_jobs, df_power)
    print(df_jobs_aggmetrics[["run_time", 
                              "num_nodes", 
                              "total_power_max_watts", 
                              "total_power_mean_watts",
                              "total_power_median_watts"]])
    save_results(df_jobs_aggmetrics, rootdir)

"""
Read Command line interface
"""
def read_cli():
    # Make parser object
    p = argparse.ArgumentParser(description='Process ExaData data to extract per-job power metrics. This script uses the output from process_marconi_jobs_2.py')
    
    p.add_argument("--rootdir", "-d", type=str, required=True,
                   help="Root directory of the trace")
    
    return(p.parse_args())

if __name__ == '__main__':
    
    if sys.version_info<(3,5,0):
        sys.stderr.write("You need python 3.5 or later to run this script\n")
        sys.exit(1)
        
    try:
        args = read_cli()        
    except:
        print('Try $python process_marconi_jobs.py --help')
        sys.exit(1)

    run_workflow(args.rootdir) 