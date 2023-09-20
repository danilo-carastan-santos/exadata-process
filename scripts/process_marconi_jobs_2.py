import argparse
import sys
import ast
import multiprocessing
import functools
import numpy as np
import pandas as pd

"""
Read data
Output from process_marconi_jobs_1.py
"""
def read_data(jobfile_single, jobfile_multi, metricfile):
    df_jobs_single = pd.read_csv(jobfile_single)
    df_jobs_multi = pd.read_csv(jobfile_multi)

    ## Here i refer to total_power but in reality it can be any metric
    df_total_power = pd.read_parquet(metricfile)
    df_total_power['node'] = pd.to_numeric(df_total_power['node'])
    df_total_power['value'] = pd.to_numeric(df_total_power['value'])
    return df_jobs_single, df_jobs_multi, df_total_power


"""
Filter 3: find the jobs that share a node
The idea is to add a new column to `df_total_power` 
with a list of jobs that run on each node at each timestamp. 
Then we filter jobs that appear sharing with another job
"""
def filter3_1_single(df_jobs_single, df_total_power):
    #removing malformed "nodes"    
    df_jobs_single["node"] = [ast.literal_eval(x)[0] for x in df_jobs_single['nodes']]

    #use this for smaller inputs
    #TEST_SAMPLE_SIZE = 1000
    
    TEST_SAMPLE_SIZE = len(df_jobs_single)
    sample = df_jobs_single[0:TEST_SAMPLE_SIZE].copy().reset_index(drop=True)

    #sample = df_jobs_single

    group = df_total_power.groupby(by="node")

    #for debugging
    #result = [group.get_group(x[0])["timestamp"].between(x[1], x[2]).value_counts() for x in sample[["node", "start_time", "end_time"]].values.tolist()]

    #i know that x[0] is node, x[1] is start_time, and x[2] is end_time
    #each element of the list is a subseries of the total_power of a certain mode
    #with "1" at the timestamps where the "job_id" ran
    result = [[group.get_group(x[0])["timestamp"].between(x[1], x[2]).astype(int).replace(0, np.nan).dropna().astype(str), x[3]] for x in sample[["node", "start_time", "end_time", "job_id"]].values.tolist()]
   
    # now i replace the "1"s with the "job_id"
    #each element of the list is a subseries of the total_power of a certain mode
    #with the "job_id" value at the timestamps where the "job_id" ran
    result2 = [x[0].replace("1.0", str(x[1])) for x in result]
    #print(result2)

    #finally i concatenate each of the series by index
    # while joining the values where indices overlap
    # i hope the indices here are consistent with the indices in df_total_power 
    #concatenated_series = pd.concat(result2).groupby(level=0).apply(','.join).replace(to_replace=r'^(0,)*0$', value="0", regex=True)
    concatenated_series = pd.concat(result2).groupby(level=0).apply(','.join).rename("job_ids")
     
    joined_total_power = df_total_power.merge(concatenated_series, left_index=True, right_index=True, how="inner")
    print(joined_total_power)
    return joined_total_power


"""
Filter 3: find the jobs that not share a node
Based on filter3_single_1, return the list of job ids that 
not shared a node with another job
"""
def filter3_2(joined_total_power):
    all_job_ids=[]
    _ = pd.Series([[all_job_ids.append(y) for y in x.split(",")] for x in joined_total_power["job_ids"].drop_duplicates().values.tolist()])

    all_job_ids = pd.Series(all_job_ids).drop_duplicates()

    nodeshare_job_ids = []
    _ = pd.Series([[nodeshare_job_ids.append(y) for y in x.split(",") if len(x.split(",")) > 1] for x in joined_total_power["job_ids"].drop_duplicates().values.tolist()])
    nodeshare_job_ids = pd.Series(nodeshare_job_ids).drop_duplicates()

    exclusive_job_ids = all_job_ids[~all_job_ids.isin(nodeshare_job_ids)] 
    print("Nodeshare Job ratio: ", len(nodeshare_job_ids)/len(all_job_ids))
    print(exclusive_job_ids)
    return exclusive_job_ids

"""
Filter 3: find the jobs that not share a node
Getting the profile of the not nodeshared jobs
And details of the exclusive jobs
"""
def filter3_3(df_jobs_single, exclusive_job_ids, joined_total_power):
    result = [x for x in joined_total_power.values if np.any(pd.Series(x[3].split(",")).isin(exclusive_job_ids).values) == True]
    df_total_power_exclusive_single = pd.DataFrame(result, columns=["timestamp", "value", "node", "job_id"])  
    df_exclusive_jobs = df_jobs_single[df_jobs_single["job_id"].isin(exclusive_job_ids.astype(int))]
    return df_total_power_exclusive_single, df_exclusive_jobs

"""
Filter 3: Define the function to check the condition in parallel
"""
def check_condition_f3(x, exclusive_job_ids=None):
    return np.any(pd.Series(x[3].split(",")).isin(exclusive_job_ids).values)

"""
Filter 3: find the jobs that not share a node
Getting the profile of the not nodeshared jobs
And details of the exclusive jobs
Attempt to do this in parallel
"""
def filter3_3_par(df_jobs, exclusive_job_ids, joined_total_power):
    # Use multiprocessing.Pool to parallelize the list comprehension
    pool = multiprocessing.Pool()
    result = pool.map(functools.partial(check_condition_f3, exclusive_job_ids=exclusive_job_ids), joined_total_power.values)

    # Filter the values based on the condition
    result = [x for x, res in zip(joined_total_power.values, result) if res]

    df_total_power_exclusive_single = pd.DataFrame(result, columns=["timestamp", "value", "node", "job_id"])  
    df_exclusive_jobs = df_jobs[df_jobs["job_id"].isin(exclusive_job_ids.astype(int))]
    return df_total_power_exclusive_single, df_exclusive_jobs


"""
Filter 3: find the jobs that share a node
The idea is to add a new column to `df_total_power` 
with a list of jobs that run on each node at each timestamp. 
Then we filter jobs that appear sharing with another job
Version for multi-node jobs
"""
def filter3_1_multi(df_jobs_multi, df_total_power):
    df_jobs_multi["node"] = [ast.literal_eval(x) for x in df_jobs_multi['nodes']]

    #use this for smaller inputs
    #TEST_SAMPLE_SIZE = 1000

    TEST_SAMPLE_SIZE = len(df_jobs_multi)
    sample = df_jobs_multi[0:TEST_SAMPLE_SIZE].copy().reset_index(drop=True)

    #sample = df_jobs_single

    group = df_total_power.groupby(by="node")

    #for debugging
    #result = [group.get_group(x[0])["timestamp"].between(x[1], x[2]).value_counts() for x in sample[["node", "start_time", "end_time"]].values.tolist()]

    #i know that x[0] is the node list, x[1] is start_time, and x[2] is end_time
    #each element of the list is a subseries of the total_power of a certain mode
    #with "1" at the timestamps where the "job_id" ran
    # i replace the "0"s (where the timestamp is not betweenx[1], x[2]) with nans just to remove these values with dropna.
    result = [[[group.get_group(y)["timestamp"].between(x[1], x[2]).astype(int).replace(0, np.nan).dropna().astype(str) for y in x[0]], x[3]] for x in sample[["node", "start_time", "end_time", "job_id"]].values.tolist()]

    #print(type(group.get_group(512)))
    #group.get_group(x[0])

    #result[0] = Series with timestamps with True where the job run, and False otherwise
    #result[1] = job id
    #result.values.to_list()

    # now i replace the "1"s with the "job_id"
    #each element of the list is a subseries of the total_power of a certain mode
    #with the "job_id" value at the timestamps where the "job_id" ran
    result2 = [pd.concat([y.replace("1.0", str(x[1])) for y in x[0]]) for x in result]

    #finally i concatenate each of the series by index
    # while joining the values where indices overlap
    # i hope the indices here are consistent with the indices in df_total_power 
    #concatenated_series = pd.concat(result2).groupby(level=0).apply(','.join).replace(to_replace=r'^(0,)*0$', value="0", regex=True)
                
    concatenated_series = pd.concat(result2).groupby(level=0).apply(','.join).rename("job_ids")
    #print(concatenated_series)

    # use the below code for the full run
    #joined_total_power = df_total_power.merge(concatenated_series, left_index=True, right_index=True, how="left")

    #use the below code for a rest run
    joined_total_power = df_total_power.merge(concatenated_series, left_index=True, right_index=True, how="inner")
    print(joined_total_power)
    return joined_total_power

"""
Save results to csv
"""
def save_results(df_exclusive_jobs_single, df_exclusive_jobs_multi, df_total_power_exclusive_single, df_total_power_exclusive_multi, jobfile_single, metricfile):   
    metric = metricfile.split("/")[-2] 
    jobfile_out = jobfile_single.rstrip(metric+"_filter12_singlenode.csv")     
    metricfile_out = metricfile.rstrip("a_0.parquet")
    df_exclusive_jobs_single.to_csv(jobfile_out+metric+"_filter123_singlenode.csv", index=False)
    df_exclusive_jobs_multi.to_csv(jobfile_out+metric+"_filter123_multinode.csv", index=False)
    df_total_power_exclusive_single.to_csv(metricfile_out+"a_0_filter123_singlenode.csv", index=False)
    df_total_power_exclusive_multi.to_csv(metricfile_out+"a_0_filter123_multinode.csv", index=False)


"""
Run workflow
"""
def run_workflow(metricfile, jobfile_single, jobfile_multi):
    df_jobs_single, df_jobs_multi, df_total_power = read_data(jobfile_single, jobfile_multi, metricfile)
    #Single-node jobs workflow    
    joined_total_power = filter3_1_single(df_jobs_single, df_total_power)
    exclusive_job_ids = filter3_2(joined_total_power)
    #df_total_power_exclusive_single, df_exclusive_jobs_single = filter3_single_3(df_jobs_single, exclusive_job_ids, joined_total_power)
    df_total_power_exclusive_single, df_exclusive_jobs_single = filter3_3_par(df_jobs_single, exclusive_job_ids, joined_total_power)
    print(df_total_power_exclusive_single)
    print(df_exclusive_jobs_single)
    ###############################
    #Multi-node jobs workflow
    joined_total_power = filter3_1_multi(df_jobs_multi, df_total_power)
    exclusive_job_ids = filter3_2(joined_total_power)
    #df_total_power_exclusive_single, df_exclusive_jobs_single = filter3_single_3(df_jobs_single, exclusive_job_ids, joined_total_power)
    df_total_power_exclusive_multi, df_exclusive_jobs_multi = filter3_3_par(df_jobs_multi, exclusive_job_ids, joined_total_power)
    print(df_total_power_exclusive_multi)
    print(df_exclusive_jobs_multi)
    save_results(df_exclusive_jobs_single, df_exclusive_jobs_multi, df_total_power_exclusive_single, df_total_power_exclusive_multi, jobfile_single, metricfile)
    ###############################

"""
Read Command line interface
"""
def read_cli():
    # Make parser object
    p = argparse.ArgumentParser(description='Process ExaData data to extract per-job energy profiles')
    
    p.add_argument("--metricfile", "-m", type=str, required=True,
                   help="Metric file")
    p.add_argument("--jobfilesingle", "-js", type=str, required=True,
                   help="Job table file for single-node jobs (output from process_marconi_jobs_1.py)")
    p.add_argument("--jobfilemulti", "-jm", type=str, required=True,
                   help="Job table file for multi-node jobs (output from process_marconi_jobs_1.py)")
    
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

    run_workflow(args.metricfile, args.jobfilesingle, args.jobfilemulti) 