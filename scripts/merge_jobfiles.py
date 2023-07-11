import glob
import pandas as pd
import sys
import argparse

"""
Read job files spread in the months folders
"""
def read_jobifles(rootdir):
    #DATASET_PATH = "/home/dancarastan/Documentos/exadata_job_energy_profiles/"

    jobfiles_list = glob.glob(rootdir+"*"+"/plugin=job_table"+"/metric=job_info_marconi100"+"/a_0_filter123_aggmetrics.csv")

    #print(len(jobfiles_list))
    df_jobs = pd.concat([pd.read_csv(jobfile) for jobfile in jobfiles_list]).reset_index(drop=True)
    return df_jobs


"""
Save results to compressed csv
"""
def save_results(df_jobs, rootdir):
    df_jobs.to_csv(rootdir+"/filter123_all_jobs_aggmetrics.csv.gz", index=False)


"""
Run workflow
"""
def run_workflow(rootdir):
    df_jobs = read_jobifles(rootdir)
    save_results(df_jobs, rootdir)


"""
Read Command line interface
"""
def read_cli():
    # Make parser object
    p = argparse.ArgumentParser(description='Concatenate job table files into a single csv file')
    
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