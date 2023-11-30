#!/usr/bin/env python3
import sys
import argparse
import ast
import pandas as pd
import numpy as np

NB_GPUS = 4

"""
Read Data
"""
def read_data(jobfile, pluginpath):
    df_jobs = pd.read_parquet(jobfile)    
    power_filepaths = [pluginpath+"/metric=Gpu"+str(x)+"_power_usage/a_0.parquet" for x in range(NB_GPUS)]

    df_power = pd.concat([pd.read_parquet(x).assign(gpu=y) for x, y in zip(power_filepaths, range(NB_GPUS))]).reset_index(drop=True)

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
Filter 0: get gpu jobs
only take jobs with proper tres_per_node
"""
def filter0(df_jobs):
    allowed_tres_values =  ["gres:gpu:0", "gres:gpu:1", "gres:gpu:2", "gres:gpu:3", "gres:gpu:4"]
    df_jobs_f0 = df_jobs[df_jobs["tres_per_node"].isin(allowed_tres_values)].copy()

    df_jobs_f0["gpus_per_node"] = df_jobs_f0["tres_per_node"].str.replace("gres:gpu:", "").astype("int32")
    print("Number of jobs after filter 0: ", str(len(df_jobs_f0)))
    return df_jobs_f0


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
Method for single-node jobs. the method looks at all gpus in the node, and not per gpu in isolation
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
Method for multi-node jobs. the method looks at all gpus in the node, and not per gpu in isolation
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
def save_results(df_jobs_single, df_jobs_multi, jobfile):    
    jobfile_out = jobfile.rstrip("a_0.parquet")
    # hard-coded metric = gpu_power_usage
    #metric = metricfile.split("/")[-2]
    metric = "gpu_power_usage"    
    df_jobs_single.to_csv(jobfile_out+metric+"_filter12_singlenode.csv", index=False)
    df_jobs_multi.to_csv(jobfile_out+metric+"_filter12_multinode.csv", index=False)

"""
Run workflow
"""
def run_workflow(pluginpath, jobfile):
    df_jobs, df_power = read_data(jobfile=jobfile, pluginpath=pluginpath)
    df_jobs, df_power = preprocess_data(df_jobs=df_jobs, df_power=df_power)
    df_jobs = filter0(df_jobs)
    df_jobs = filter1(df_jobs)
    df_jobs_single = filter2_single(df_jobs, df_power)
    df_jobs_multi = filter2_multi(df_jobs, df_power)
    save_results(df_jobs_single, df_jobs_multi, jobfile)    

"""
Read Command line interface
"""
def read_cli():
    # Make parser object
    p = argparse.ArgumentParser(description='Process ExaData data to extract per-job energy profiles')    
    
    p.add_argument("--pluginpath", "-p", type=str, required=True,
                   help="Path of the 'plugin=ganglia_pub' directory, containing the 'metric=GpuX_power_usage' directories")
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

    run_workflow(args.pluginpath, args.jobfile)    