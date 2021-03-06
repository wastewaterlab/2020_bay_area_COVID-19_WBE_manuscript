import pandas as pd
import numpy as np
from scipy import stats as sci
from scipy.stats.mstats import gmean
from scipy.stats import gstd

def calculate_gc_per_l(qpcr_data ):
    '''
    calculates and returns gene copies / L

    Params
    replace_bloq should the function replace any sample that is below the limit of quantification with the loq
    qpcr_data-- dataframe with qpcr technical triplicates averaged. Requires the columns
            gc_per_ul_input
            Quantity_mean
            template_volume
            elution_vol_ul
            weight_vol_extracted_ml
        if replace_bloq is true
            bloq
            lowest_std_quantity

    Returns
    qpcr_data: same data, with additional column
    gc_per_L
    '''
    # if replace_bloq:
    #     qpcr_data.loc[qpcr_data.bloq==True, "Quantity_mean"]= qpcr_data.lowest_std_quantity


    # calculate the conc of input to qPCR as gc/ul
    qpcr_data['gc_per_ul_input'] = qpcr_data['Quantity_mean'].astype(float) / qpcr_data['template_volume'].astype(float)

    # multiply input conc (gc / ul) by elution volume (ul) and divide by volume concentrated (mL). Multiply by 1000 to get to gc / L.
    qpcr_data['gc_per_L']= np.nan
    qpcr_data.loc[qpcr_data.blod_master_curve== True, 'gc_per_L'] = 1000 * qpcr_data['gc_per_ul_input'].astype(float) * qpcr_data['elution_vol_ul'].astype(float) / 50
    qpcr_data.loc[qpcr_data.blod_master_curve!= True, 'gc_per_L'] = 1000 * qpcr_data['gc_per_ul_input'].astype(float) * qpcr_data['elution_vol_ul'].astype(float) / qpcr_data['weight_vol_extracted_ml'].astype(float)


    return qpcr_data['gc_per_L']


def normalize_to_pmmov(qpcr_data, replace_bloq= False):

    '''
    calculates a normalized mean to pmmov when applicable and returns dataframe with new columns

      Params
        replace_bloq should the function replace any sample that is below the limit of quantification with the loq
        values the values to replace the bloq values with (should be lower than the loq)
        qpcr_data-- dataframe with qpcr technical triplicates averaged. Requires the columns
                Target
                Quantity_mean
                Sample
                Task
            if replace_bloq is true
                bloq
                lowest_std_quantity
      Returns
      qpcr_m: same data, with additional columns
            mean_normalized_to_pmmov: takes every column and divides by PMMoV that is associated with that sample name (so where target == PMMoV it will be 1)
            log10mean_normalized_to_log10pmmov: takes the log10 of N1 and the log 10 of PMMoV then normalizes
            log10_mean_normalized_to_pmmov: takes the log10 of mean_normalized_to_pmmov
    '''
    if replace_bloq:
        qpcr_data.loc[qpcr_data.bloq==True, "Quantity_mean"]= qpcr_data.lowest_std_quantity

    pmmov=qpcr_data[qpcr_data.Target=='PMMoV']
    pmmov=pmmov[['Quantity_mean','Sample','Task']]
    pmmov.columns=['pmmov_mean',  "Sample", "Task"]
    qpcr_m=qpcr_data.merge(pmmov, how='left', on=["Sample", "Task"])
    qpcr_m["mean_normalized_to_pmmov"] = qpcr_m['Quantity_mean']/qpcr_m['pmmov_mean']
    qpcr_m["log10mean_normalized_to_log10pmmov"] = np.log10(qpcr_m['Quantity_mean'])/np.log10(qpcr_m['pmmov_mean'])
    qpcr_m['log10_mean_normalized_to_pmmov']=np.log10(qpcr_m['mean_normalized_to_pmmov'])

    return qpcr_m

def xeno_inhibition_test(qpcr_data,qpcr_normd, x=1):
  '''
        Calculates the difference in Ct compared to the NTC for xeno inhibition test, outputs a list of inhibited samples

          Params
            optional x: the dCt defined as inhibited
            qpcr_data (main dfm)
            qpcr_data_xeno-- dataframe with qpcr technical triplicates averaged. Requires the columns
                    Target (includes xeno)
                    plate_id
                    Well
                    Quantity_mean
                    Sample
                    Task
          Returns
          qpcr_data with is_inhibited column
          xeno_fin_all -- calculates the difference in Ct values of the negative control (spiked with xeno) to the sample spiked with xeno, adds column for inhibited (Yes or No)
          ntc_col -- all of the negative control values for xeno
  '''

  #Find targets other than xeno for each well+plate combination
  p_w_targets=qpcr_data[qpcr_data.Target!='Xeno'].copy()
  p_w_targets['p_id']=p_w_targets.plate_id.astype('str').str.cat(p_w_targets.Well.astype('str'), sep ="_")
  p_w_targets=p_w_targets.groupby('p_id')['Target'].apply(lambda targs: ','.join(targs)).reset_index()
  p_w_targets.columns=['p_id','additional_target']

  #subset out xeno samples, merge with previous, use to calculate mean and std
  target=qpcr_data[(qpcr_data.Target=='Xeno')].copy() #includes NTC & stds
  target['p_id']=qpcr_data.plate_id.astype('str').str.cat(qpcr_data.Well, sep ="_")
  target=target.merge(p_w_targets, how='left', on='p_id')
  if target.additional_target.astype('str').str.contains(',').any():
      print(target.additional_target.unique())
      raise ValueError('Error: update function, more than 2 multiplexed targets or one of the two multiplexed targets is not xeno')

  target_s=target.groupby(["Sample","sample_full",'additional_target','plate_id','Task']).agg(Ct_vet_mean=('Cq', lambda x:  np.nan if all(np.isnan(x)) else sci.gmean(x.dropna(),axis=0)),
                                                                    Quantity_std_crv=('Quantity','max'), #just for standards
                                                                    Ct_vet_std=('Cq', lambda x: np.nan if ((len(x.dropna()) <2 )| all(np.isnan(x)) ) else (sci.gstd(x.dropna(),axis=0))),
                                                                    Ct_vet_count=('Cq','count')).reset_index()
  target=target_s[(target_s.Task!='Standard')].copy() #remove standards

  #subset and recombine to get NTC as a col
  ntc_col_c=target[target.Task=='Negative Control'].copy()
  ntc_col=ntc_col_c[["plate_id",'additional_target','Ct_vet_mean']].copy()
  ntc_col.columns=["plate_id",'additional_target','Ct_control_mean']

  ntc_col_c=ntc_col_c[["plate_id",'Task','Quantity_std_crv','additional_target','Ct_vet_mean']].copy()
  ntc_col_c.columns=["plate_id",'Task','Quantity_std_crv','additional_target','Ct_control_mean']

  std_col=target_s[target_s.Task=='Standard'].copy()
  std_col=std_col[["plate_id", 'Task','Quantity_std_crv','additional_target','Ct_vet_mean']].copy()
  std_col.columns=["plate_id",'Task','Quantity_std_crv','additional_target','Ct_control_mean']

  xeno_fin_all=target[target.Task=='Unknown'].copy()
  xeno_fin_all=xeno_fin_all.merge(ntc_col, how='left')
  xeno_fin_all["dCt"]= (xeno_fin_all["Ct_vet_mean"]- xeno_fin_all["Ct_control_mean"])
  xeno_fin_all["inhibited"]='No'
  xeno_fin_all.loc[(xeno_fin_all.dCt>x),"inhibited"]="Yes"

  ntc_std_control= ntc_col_c.append(std_col)

  inhibited=xeno_fin_all[xeno_fin_all.dCt>1].Sample.unique()
  not_inhibited=xeno_fin_all[xeno_fin_all.dCt<=1].Sample.unique()

  qpcr_normd["is_inhibited"]='unknown'
  qpcr_normd.loc[qpcr_normd.Sample.isin(inhibited),"is_inhibited"]= True
  qpcr_normd.loc[qpcr_normd.Sample.isin(not_inhibited),"is_inhibited"]= False

  return qpcr_normd, xeno_fin_all, ntc_std_control
