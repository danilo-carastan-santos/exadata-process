#!/usr/bin/env python3
import sys
import argparse
import ast
import pandas as pd
import numpy as np

"""
Read Data
"""
def read_data(jobfile, metricfile):
    df_jobs = pd.read_parquet(jobfile)
    df_power = pd.read_parquet(metricfile)
    ## I call here df_power, but in reality it can be any metric    
    return df_jobs, df_power


"""
Convert some string values to numeric
Convert timestamps to seconds for job runtime
"""
def preprocess_data(df_jobs, df_power):    
    df_power['node'] = pd.to_numeric(df_power['node'])
    df_power['value'] = pd.to_numeric(df_power['value'])
    df_jobs["run_time"] = (df_jobs['end_time']-df_jobs['start_time']) / np.timedelta64(1, 's')
    print("Total number of jobs: ", len(df_jobs))
    return df_jobs, df_power


"""
Filter 1: remove jobs that take less than a minute
"""
def filter1(df_jobs):
    SECONDS_ONE_MINUTE = 60.0

    df_jobs_f1 = df_jobs.loc[df_jobs["run_time"] >= SECONDS_ONE_MINUTE]
    print("Number of jobs after filter 1: ", str(len(df_jobs_f1)))
    return df_jobs_f1


"""
Filter 2: remove jobs with no energy profile
Method for single-node jobs
"""
def filter2_single(df_jobs, df_power):
    df_jobs_f1_single = df_jobs[df_jobs["num_nodes"]==1]

    #removing malformed "nodes"
    df_jobs_f1_single = df_jobs_f1_single[df_jobs_f1_single["nodes"].str.match("\[\d+\]")].copy().reset_index(drop=True)
    df_jobs_f1_single["node"] = [ast.literal_eval(x)[0] for x in df_jobs_f1_single['nodes']]

    #use this for smaller inputs
    #sample = df_jobs_f1_single[0:10000].copy().reset_index(drop=True)

    sample = df_jobs_f1_single

    group = df_power.groupby(by="node")

    available_nodes = group.groups.keys()    
 
    #for debugging
    #result = [group.get_group(x[0])["timestamp"].between(x[1], x[2]).value_counts() for x in sample[["node", "start_time", "end_time"]].values.tolist()]

    #i know that 0 is node, 1 is start_time, and 2 is end_time
    result = [any(group.get_group(x[0])["timestamp"].between(x[1], x[2])) if x[0] in available_nodes else False for x in sample[["node", "start_time", "end_time"]].values.tolist()]
    
    sample["has_profile"] = result
    df_jobs_f12_single = sample[sample["has_profile"]==True]

    print("Number of jobs after filter 2 - single: ", str(len(df_jobs_f12_single)))
    return df_jobs_f12_single


"""
Filter 2: remove jobs with no energy profile
Method for multi-node jobs
"""
def filter2_multi(df_jobs, df_power):    
    df_jobs_f1_multi = df_jobs[df_jobs["num_nodes"] > 1].copy().reset_index(drop=True)

    #removing malformed "nodes"   
    df_jobs_f1_multi["node"] = [ast.literal_eval(x) for x in df_jobs_f1_multi['nodes']]
    
    #use this for smaller inputs
    #sample = df_jobs_f1_multi[0:10].copy().reset_index(drop=True)

    sample = df_jobs_f1_multi

    group = df_power.groupby(by="node")

    available_nodes = set(group.groups.keys())

    #for debugging
    #result = [group.get_group(x[0])["timestamp"].between(x[1], x[2]).value_counts() for x in sample[["node", "start_time", "end_time"]].values.tolist()]

    #i know that 0 is node, 1 is start_time, and 2 is end_time
    result = [all([any(group.get_group(y)["timestamp"].between(x[1], x[2])) for y in x[0]]) if set(x[0]).issubset(available_nodes) else False for x in sample[["node", "start_time", "end_time"]].values.tolist()]

    sample["has_profile"] = result
    df_jobs_f12_multi = sample[sample["has_profile"]==True]
    print("Number of jobs after filter 2 - multi: ", str(len(df_jobs_f12_multi)))
    return df_jobs_f12_multi


"""
Save intermediate results to csv
"""
def save_results(df_jobs_single, df_jobs_multi, jobfile, metricfile):    
    jobfile_out = jobfile.rstrip("a_0.parquet")
    metric = metricfile.split("/")[-2]    
    df_jobs_single.to_csv(jobfile_out+metric+"_filter12_singlenode.csv", index=False)
    df_jobs_multi.to_csv(jobfile_out+metric+"_filter12_multinode.csv", index=False)

"""
Run workflow
"""
def run_workflow(metricfile, jobfile):
    df_jobs, df_power = read_data(jobfile=jobfile, metricfile=metricfile)
    df_jobs, df_power = preprocess_data(df_jobs=df_jobs, df_power=df_power)
    df_jobs = filter1(df_jobs)
    df_jobs_single = filter2_single(df_jobs, df_power)
    df_jobs_multi = filter2_multi(df_jobs, df_power)
    save_results(df_jobs_single, df_jobs_multi, jobfile, metricfile)    

"""
Read Command line interface
"""
def read_cli():
    # Make parser object
    p = argparse.ArgumentParser(description='Process ExaData data to extract per-job energy profiles')    
    
    p.add_argument("--metricfile", "-m", type=str, required=True,
                   help="Metric file")
    p.add_argument("--jobfile", "-j", type=str, required=True,
                   help="Job table file")
    
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

    run_workflow(args.metricfile, args.jobfile)    