
import pandas as pd
import numpy  as np

def get_extraction_control(qpcr_averaged):
    '''
    make column for PBS controls assessment
    Params
        qpcr_averaged df, with columns:
        'plate_id', 'batch', 'Target' and 'Cq_init_min'
    Returns
        qpcr_averaged df without rows for PBS controls
        with new column 'PBS_result' for the PBS extraction batch control
    '''

    # filter for just PBS controls and specific columns
    pbs = qpcr_averaged[qpcr_averaged.interceptor == 'PBS'].copy()
    pbs.Cq_init_min = pd.to_numeric(pbs.Cq_init_min)

    # make PBS_result column "negative" if Cq was NaN/nondetect
    # or equal to Cq_min of PBS if detected

    # if a batch had multiple PBS controls, choose the one with the lowest Cq to represent the batch (so that if there was contamination we will see it)
    pbs = pbs.groupby(['batch', 'Target', 'plate_id']).agg(
                                                           Cq_init_min=('Cq_init_min','min')).reset_index()
    pbs['PBS_result'] = np.nan
    pbs.loc[np.isnan(pbs.Cq_init_min), 'PBS_result'] = 'negative'
    pbs.loc[~np.isnan(pbs.Cq_init_min), 'PBS_result'] = pbs.Cq_init_min

    pbs = pbs[['plate_id', 'batch', 'Target', 'PBS_result']]

    # filter out pbs controls from main dataset then merge pbs df
    qpcr_averaged = qpcr_averaged[qpcr_averaged.interceptor != 'PBS'].copy()
    qpcr_averaged = qpcr_averaged.merge(pbs, how = 'left', on = ['plate_id', 'batch', 'Target'])

    # make sure date_sampling is still datetime (sometime gets messed up with merges)
    qpcr_averaged.date_sampling = pd.to_datetime(qpcr_averaged.date_sampling)

    return(qpcr_averaged)
