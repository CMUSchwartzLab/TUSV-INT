# Input: 
#       -d: sample.vcf in a patient folder
# Author: Jingyi Wang
# Created date: 2017_09_25
# Modified date: 2017_10_02

##################
##### IMPORT #####
##################

import sys      
import os       
import argparse 
import vcf      
import numpy as np
import operator
import random
import pandas as pd 

# custom imports
import file_manager as fm

#####################
##### FUNCTIONS #####
#####################

#  input: in_dir (str) full path to input directory containing .vcf file(s)
# output: bp_attr (dict) key is breakpoint index. val is tuple (chrm (str), pos (int), extends_left (bool))
#         cv_attr (dict) key (int) is segment index. val is tuple (chrm (str), bgn_pos (int), end_pos (int))
def get_mats(in_dir, scrna_file, n, const=120, sv_ub=80):
    sampleList = fm._fnames_with_extension(in_dir, '.vcf')

    m = len(sampleList)
    sampleList.sort()

    bp_id_to_mate_id, bp_id_to_tuple = {}, {}

    BP_sample_dict, CN_sample_dict, CN_sample_rec_dict, CN_sample_rec_dict_minor, CN_sample_rec_dict_major = dict(), dict(), dict(), dict(), dict()
    SNV_sample_dict = {}
    for i, sample in enumerate(sampleList):
        input_vcf_file = in_dir + '/' + sample
        reader = vcf.Reader(open(input_vcf_file, 'r'))
        scrna_df = pd.read_csv(scrna_file,sep='\t')
        
        BP_sample_dict[sample], CN_sample_dict[sample], CN_sample_rec_dict[sample], CN_sample_rec_dict_minor[sample], CN_sample_rec_dict_major[sample], mateIDs, toTuple, SNV_sample_dict[sample], C_RNA = get_sample_dict(reader, scrna_df)
        # prepend sample index to each breakpoint ID
        #print(sample, (BP_sample_dict[sample].items()))
        for k, v in mateIDs.iteritems():
            bp_id_to_mate_id[str(i+1) + k] = str(i+1) + v # add all entries from mateIDs (dict) to bp_id_to_mate_id (dict)
            bp_id_to_tuple[str(i+1) + k] = toTuple[k]     # add all entries from toTuple (dict) to bp_id_to_tuple (dict)

    BP_idx_dict, l = get_BP_idx_dict(BP_sample_dict)
    G = make_G(BP_idx_dict, bp_id_to_mate_id, bp_id_to_tuple)
    CN_startPos_dict, CN_endPos_dict, r = get_CN_indices_dict(CN_sample_dict)
    #print(CN_startPos_dict, CN_endPos_dict)
    SNV_idx_dict, g = get_snv_idx_dict(SNV_sample_dict)
    #print(g)

    F_phasing, F_unsampled_phasing, G, G_unsampled, Q, Q_unsampled, A, H, cv_attr, F_info_phasing, F_unsampled_info_phasing, sampled_snv_list_sort, \
    unsampled_snv_list_sort, sampled_sv_list_sort, unsampled_sv_list_sort \
        = make_matrices(m, n, l, g, r, G, sampleList, BP_sample_dict, BP_idx_dict, SNV_sample_dict, SNV_idx_dict, CN_sample_rec_dict, CN_sample_rec_dict_minor, CN_sample_rec_dict_major, CN_startPos_dict, CN_endPos_dict, const=const, sv_ub=sv_ub)
    bp_attr = _inv_dic(BP_idx_dict)

    F_phasing = np.array(F_phasing).astype(float)
    F_unsampled_phasing = np.array(F_unsampled_phasing).astype(float)
    F_info_phasing = np.array(F_info_phasing)
    F_unsampled_info_phasing = np.array(F_unsampled_info_phasing)
    Q = np.array(Q)
    Q_unsampled = np.array(Q_unsampled)


    abnormal_idx = np.where(np.sum(Q, 1) == 0)[0]
    l_ab_s = len(abnormal_idx[abnormal_idx < l])
    g_ab_s = len(abnormal_idx[abnormal_idx >= (l)])
    print("The mutations at ", abnormal_idx, " will be removed due to non-existing bp in CNV")
    #F = np.delete(F, abnormal_idx, axis=1)
    sampled_sv_list_sort = np.delete(sampled_sv_list_sort, abnormal_idx[abnormal_idx < l])
    sampled_snv_list_sort = np.delete(sampled_snv_list_sort, abnormal_idx-l)
    F_phasing = np.delete(F_phasing, abnormal_idx, axis=1)
    F_info_phasing = np.delete(F_info_phasing, abnormal_idx, axis=0)
    
    Q = np.delete(Q, abnormal_idx, axis=0)
    G = np.delete(G, abnormal_idx, axis=0)
    G = np.delete(G, abnormal_idx, axis=1)
    
    #sys.stdout.flush()
    A = np.array(A)
    H = np.array(H)

    abnormal_idx2 = np.where(np.sum(G, 0) != 2)[0]
    l_ab_s += len(abnormal_idx2)
    
    print("The mutations at ", abnormal_idx2, " will be removed due to non-paired breakpoints")
    # F = np.delete(F, abnormal_idx2, axis=1)
    sampled_sv_list_sort = np.delete(sampled_sv_list_sort, abnormal_idx2)
    
    F_phasing = np.delete(F_phasing, abnormal_idx2, axis=1)
    F_info_phasing = np.delete(F_info_phasing, abnormal_idx2, axis=0)
    Q = np.delete(Q, abnormal_idx2, axis=0)
    G = np.delete(G, abnormal_idx2, axis=0)
    G = np.delete(G, abnormal_idx2, axis=1)
    
    
    abnormal_idx22 = np.where(np.sum(G, 1) != 2)[0]
    l_ab_s += len(abnormal_idx22)
    print("The mutations at ", abnormal_idx22, " will be removed due to non-paired breakpoints")
    # F = np.delete(F, abnormal_idx2, axis=1)
    sampled_sv_list_sort = np.delete(sampled_sv_list_sort, abnormal_idx22)
    F_phasing = np.delete(F_phasing, abnormal_idx22, axis=1)
    F_info_phasing = np.delete(F_info_phasing, abnormal_idx22, axis=0)
    Q = np.delete(Q, abnormal_idx22, axis=0)
    G = np.delete(G, abnormal_idx22, axis=0)
    G = np.delete(G, abnormal_idx22, axis=1)
    
    
    l_un = len(unsampled_sv_list_sort)
    g_un = len(unsampled_snv_list_sort)
    
    abnormal_idx_unsampled = np.where(np.sum(Q_unsampled, 1) == 0)[0]
    l_ab_un = len(abnormal_idx_unsampled[abnormal_idx_unsampled < l_un])
    g_ab_un = len(abnormal_idx_unsampled[abnormal_idx_unsampled >= l_un])
    
    print("The mutations at ", abnormal_idx_unsampled, " will be removed due to non-existing position for unsampled SNVs in CNV")
    # F = np.delete(F, abnormal_idx, axis=1)
    F_unsampled_phasing = np.delete(F_unsampled_phasing, abnormal_idx_unsampled, axis=1)
    F_unsampled_info_phasing = np.delete(F_unsampled_info_phasing, abnormal_idx_unsampled, axis=0)
    Q_unsampled = np.delete(Q_unsampled, abnormal_idx_unsampled, axis=0) ## nb 
    G_unsampled = np.delete(G_unsampled, abnormal_idx_unsampled, axis=0) ## nb 
    G_unsampled = np.delete(G_unsampled, abnormal_idx_unsampled, axis=1) ## nb 
    
    unsampled_sv_list_sort = np.delete(unsampled_sv_list_sort, abnormal_idx_unsampled[abnormal_idx_unsampled < l_un])
    unsampled_snv_list_sort = np.delete(unsampled_snv_list_sort, abnormal_idx_unsampled-l_un)
    
    l_g, r = Q.shape
    l, _ = G.shape
    g = l_g - l
    A = A[0:m, 0:l] #empty matrix
    H = H[0:m, 0:l]
    return F_phasing, F_unsampled_phasing, Q, Q_unsampled, G, G_unsampled, A, H, bp_attr, cv_attr, F_info_phasing, F_unsampled_info_phasing, sampled_snv_list_sort, unsampled_snv_list_sort, sampled_sv_list_sort, unsampled_sv_list_sort, C_RNA, l_ab_s, g_ab_s,l_ab_un, g_ab_un


#  input: bp_id_to_mate_id
#         BP_idx_dict[(chrom, pos, direction)] == bp_index
# output: chrms (list of str) chromosome for each breakpoint in order of breakpoint index
#         poss (list of int) position on chromosome for each breakpoint in order ...
#         oris (list of bool) True if break end extends to the left in original genome. False otherwise
def _get_bp_attr(BP_idx_dict):
    inv_BP_idx_dict = _inv_dic(BP_idx_dict) # keys are now index of breakpoints
    chrms, poss, oris, mate_idxs = [], [], [], []
    for i in sorted(inv_BP_idx_dict.iterkeys()):
        chrm, pos, ori = inv_BP_idx_dict[i]
        chrms.append(chrm)
        poss.append(pos)
        oris.append(ori)
    return chrms, poss, oris


# init a r*c 2d list filling with 0
def make_2d_list(r,c):
    result = list()
    for i in range(r):
        result.append([0] * c)
    return result

def make_3d_list(r,c,d):
    result = list()
    for i in range(r):
        temp = []
        for j in range(c):
            temp.append([0] * d)
        result.append(temp)
    return result

# output: cv_attr (dict) key (int) is segment index. val is tuple (chrm (str), bgn_pos (int), end_pos (int))
def make_matrices(m, n, l, g, r, G, sampleList, BP_sample_dict, BP_idx_dict,  SNV_sample_dict, SNV_idx_dict, CN_sample_rec_dict, \
                  CN_sample_rec_dict_minor, CN_sample_rec_dict_major, CN_startPos_dict, CN_endPos_dict, const=120, sv_ub=80):

    if sv_ub < 0:
        sampled_sv_idx_list_sorted = np.arange(len(BP_idx_dict))
        unsampled_sv_idx_list_sorted = np.array([])
        G_sampled=G
        G_unsampled=None
        if l + g <= const:
            F_phasing, Q, A, H = np.zeros((m, l + g + 2 * r)), np.zeros((l + g, r)), \
                                 np.zeros((m, l)), np.zeros((m, l))
            F_unsampled_phasing, Q_unsampled = None, None
            F_info_phasing = make_2d_list(l + g + 2 * r, 3)
            F_SV = F_phasing[:, :l]
            F_SV_info = F_info_phasing[:l]
            F_SNV = F_phasing[:, l:(l + g)]
            F_SNV_info = F_info_phasing[l:(l + g)]
            F_SNV_unsampled = None
            F_SNV_unsampled_info = None
            Q_unsampled = None
            F_CNV = F_phasing[:, (l + g):]
            F_CNV_info = F_info_phasing[(l + g):]

            # for (chrom, pos), snv_idx in SNV_idx_dict.items():
            #     F_SNV_info[snv_idx][0] = chrom
            #     F_SNV_info[snv_idx][1] = pos
            #     F_SNV_info[snv_idx][2] = "snv_" + str(snv_idx)
            sampled_snv_idx_list_sorted = np.arange(len(SNV_idx_dict))
            unsampled_snv_idx_list_sorted = np.array([])
        elif l <= const:
            F_phasing, F_unsampled_phasing, Q, Q_unsampled, A, H = np.zeros((m, const + 2 * r)), np.zeros((m, l + g - const)), \
            np.zeros((const, r)), np.zeros((l + g - const, r)), np.zeros((m, l)), np.zeros((m, l))
            F_info_phasing, F_unsampled_info_phasing = make_2d_list(const + 2 * r, 3), make_2d_list(l + g - const, 3)
            F_SV = F_phasing[:, :l]
            F_SV_info = F_info_phasing[:l]
            Q_SV = Q[:l]
            F_SNV = F_phasing[:, l:const]
            F_SNV_info = F_info_phasing[l:const]
            Q_SNV = Q[l:]
            F_SNV_unsampled = F_unsampled_phasing
            F_SNV_unsampled_info = F_unsampled_info_phasing
            Q_SNV_unsampled = Q_unsampled
            F_CNV = F_phasing[:, const:]
            F_CNV_info = F_info_phasing[const:]
            sampled_snv_idx_list_sorted = []
            sampled_list = np.random.choice(a=len(SNV_idx_dict), size=const - l, replace=False)
            unsampled_snv_idx_list_sorted = []
            for i in np.arange(len(SNV_idx_dict)):
                if i in sampled_list:
                    sampled_snv_idx_list_sorted.append(i)
                else:
                    unsampled_snv_idx_list_sorted.append(i)
            sampled_snv_idx_list_sorted = np.array(sampled_snv_idx_list_sorted)
            unsampled_snv_idx_list_sorted = np.array(unsampled_snv_idx_list_sorted)

        elif l > const:
            F_phasing, F_unsampled_phasing, Q, Q_unsampled, A, H = np.zeros((m, l + 2 * r)), np.zeros((m, g)), np.zeros(
                (l, r)), np.zeros((g, r)), np.zeros((m, l)), np.zeros((m, l))
            F_info_phasing, F_unsampled_info_phasing = make_2d_list(l + 2 * r, 3), make_2d_list(g, 3)
            F_SV = F_phasing[:, :l]
            F_SV_info = F_info_phasing[:l]
            Q_SV = Q[:l]
            F_SNV = None
            F_SNV_info = None
            Q_SNV = None
            F_SNV_unsampled = F_unsampled_phasing
            F_SNV_unsampled_info = F_unsampled_info_phasing
            Q_SNV_unsampled = Q_unsampled
            F_CNV = F_phasing[:, l:]
            F_CNV_info = F_info_phasing[l:]
            # for (chrom, pos), snv_idx in SNV_idx_dict.items():
            #     F_SNV_unsampled_info[snv_idx][0] = chrom
            #     F_SNV_unsampled_info[snv_idx][1] = pos
            #     F_SNV_unsampled_info[snv_idx][2] = "snv_" + str(snv_idx)
            sampled_snv_idx_list_sorted = np.array([])
            unsampled_snv_idx_list_sorted = np.arange(len(SNV_idx_dict))
        else:
            raise Exception("Error during making matrices")
    else:
        assert sv_ub <= const
        if l <= sv_ub and l + g <= const:
            F_phasing, Q, A, H = np.zeros((m, l + g + 2 * r)), np.zeros((l + g,r)), \
                                    np.zeros((m, l)), np.zeros((m, l))
            F_unsampled_phasing, Q_unsampled = None, None
            F_info_phasing = make_2d_list(l + g + 2 * r, 3)
            F_SV = F_phasing[:,:l]
            F_SV_info = F_info_phasing[:l]
            F_SNV = F_phasing[:,l:(l+g)]
            F_SNV_info = F_info_phasing[l:(l + g)]
            F_SNV_unsampled = None
            F_SNV_unsampled_info = None
            F_CNV = F_phasing[:,(l+g):]
            F_CNV_info = F_info_phasing[(l+g):]
            Q_unsampled = None
            # for (chrom, pos), snv_idx in SNV_idx_dict.items():
            #     F_SNV_info[snv_idx][0] = chrom
            #     F_SNV_info[snv_idx][1] = pos
            #     F_SNV_info[snv_idx][2] = "snv_" + str(snv_idx)
            sampled_sv_idx_list_sorted = np.arange(len(BP_idx_dict))
            unsampled_sv_idx_list_sorted = np.array([])
            sampled_snv_idx_list_sorted = np.arange(len(SNV_idx_dict))
            unsampled_snv_idx_list_sorted = np.array([])
        elif l <= sv_ub and l + g > const:
            F_phasing, F_unsampled_phasing, Q, Q_unsampled, A, H = np.zeros((m, const + 2 * r)), np.zeros((m, l + g - const )), \
                np.zeros((const, r)), np.zeros((l + g - const, r)), np.zeros((m, l)), np.zeros((m, l))
            F_info_phasing, F_unsampled_info_phasing = make_2d_list(const + 2 * r, 3), make_2d_list(l + g - const, 3)
            F_SV = F_phasing[:,:l]
            F_SV_info = F_info_phasing[:l]
            Q_SV = Q[:l]
            F_SNV = F_phasing[:,l:const]
            F_SNV_info = F_info_phasing[l:const]
            Q_SNV = Q[l:]
            F_SNV_unsampled = F_unsampled_phasing
            F_SNV_unsampled_info = F_unsampled_info_phasing
            Q_SNV_unsampled = Q_unsampled
            F_CNV = F_phasing[:,const:]
            F_CNV_info = F_info_phasing[const:]
            G_sampled = G
            G_unsampled = None
            sampled_snv_idx_list_sorted = []
            sampled_list = np.random.choice(a=len(SNV_idx_dict), size=const - l, replace=False)
            unsampled_snv_idx_list_sorted = []
            for i in np.arange(len(SNV_idx_dict)):
                if i in sampled_list:
                    sampled_snv_idx_list_sorted.append(i)
                else:
                    unsampled_snv_idx_list_sorted.append(i)
            sampled_snv_idx_list_sorted = np.array(sampled_snv_idx_list_sorted)
            unsampled_snv_idx_list_sorted = np.array(unsampled_snv_idx_list_sorted)
            sampled_sv_idx_list_sorted = np.arange(len(BP_idx_dict))
            unsampled_sv_idx_list_sorted = np.array([])

        elif l > sv_ub and l + g > const:
            F_phasing, F_unsampled_phasing, Q, Q_unsampled, A, H =  np.zeros((m, const + 2 * r)), np.zeros((m, l+g-const)), np.zeros((const, r)), \
                        np.zeros((l+g-const, r)), np.zeros((m, sv_ub)), np.zeros((m, sv_ub))
            F_info_phasing, F_unsampled_info_phasing = make_2d_list(const + 2 * r, 3), make_2d_list(l + g - const, 3)


            sampled_sv_idx_list_single = np.random.choice(a=len(BP_idx_dict), size=sv_ub // 2, replace=False)
            sampled_sv_idx_list_paired = np.where(G[sampled_sv_idx_list_single] == 1)[1]
            sampled_sv_idx_list_paired = np.array(list(set(list(sampled_sv_idx_list_paired))))
            while True:
                if len(sampled_sv_idx_list_paired) < sv_ub:
                    sampled_sv_idx_list_single = np.append(sampled_sv_idx_list_single, np.random.choice(a=len(BP_idx_dict), size=(sv_ub - len(sampled_sv_idx_list_paired)) // 2, replace=False))
                    sampled_sv_idx_list_paired = np.where(G[sampled_sv_idx_list_single] == 1)[1]
                    sampled_sv_idx_list_paired = np.array(list(set(list(sampled_sv_idx_list_paired))))
                    break
                else:
                    break

            sampled_sv_num = len(sampled_sv_idx_list_paired)
            F_SV = F_phasing[:,:sampled_sv_num]
            F_SV_info = F_info_phasing[:sampled_sv_num]
            Q_SV = Q[:sampled_sv_num]
            F_SV_unsampled = F_unsampled_phasing[:, :(l-sampled_sv_num)]
            F_SV_unsampled_info = F_unsampled_info_phasing[:(l-sampled_sv_num)]
            Q_SV_unsampled = Q_unsampled[:(l-sampled_sv_num)]
            F_SNV = F_phasing[:, sampled_sv_num:const]
            F_SNV_info = F_info_phasing[sampled_sv_num:const]
            Q_SNV = Q[sampled_sv_num:]
            F_SNV_unsampled = F_unsampled_phasing[:, (l-sampled_sv_num):]
            F_SNV_unsampled_info = F_unsampled_info_phasing[(l-sampled_sv_num):]
            Q_SNV_unsampled = Q_unsampled[(l-sampled_sv_num) : ]
            F_CNV = F_phasing[:,const:]
            F_CNV_info = F_info_phasing[const:]
            # for (chrom, pos), snv_idx in SNV_idx_dict.items():
            #     F_SNV_unsampled_info[snv_idx][0] = chrom
            #     F_SNV_unsampled_info[snv_idx][1] = pos
            #     F_SNV_unsampled_info[snv_idx][2] = "snv_" + str(snv_idx)

            sampled_sv_idx_list_sorted = []
            unsampled_sv_idx_list_sorted = []
            for i in np.arange(len(BP_idx_dict)):
                if i in sampled_sv_idx_list_paired:
                    sampled_sv_idx_list_sorted.append(i)
                else:
                    unsampled_sv_idx_list_sorted.append(i)
            sampled_sv_idx_list_sorted = np.array(sampled_sv_idx_list_sorted)
            unsampled_sv_idx_list_sorted = np.array(unsampled_sv_idx_list_sorted)
            if len(sampled_sv_idx_list_sorted) !=0: # Nishat updated Jan 25
                G_sampled = G[sampled_sv_idx_list_sorted,:][:, sampled_sv_idx_list_sorted]
            else:
                G_sampled=np.empty((0,0))
            if len(sampled_sv_idx_list_sorted) !=0: # Nishat updated Jan 25
                G_unsampled = G[unsampled_sv_idx_list_sorted,:][:, unsampled_sv_idx_list_sorted]
            else:
                G_unsampled=np.empty((0,0))
            #G_unsampled = G[unsampled_sv_idx_list_sorted,:][:, unsampled_sv_idx_list_sorted]
            sampled_snv_idx_list_sorted = []
            sampled_list = np.random.choice(a=len(SNV_idx_dict), size=const - len(sampled_sv_idx_list_sorted), replace=False)
            unsampled_snv_idx_list_sorted = []
            for i in np.arange(len(SNV_idx_dict)):
                if i in sampled_list:
                    sampled_snv_idx_list_sorted.append(i)
                else:
                    unsampled_snv_idx_list_sorted.append(i)
            sampled_snv_idx_list_sorted = np.array(sampled_snv_idx_list_sorted)
            unsampled_snv_idx_list_sorted = np.array(unsampled_snv_idx_list_sorted)

        else:
            raise Exception("Error during making matrices")

    for (chrom, pos, dir), bp_idx in BP_idx_dict.items():
        if bp_idx in sampled_sv_idx_list_sorted:
            new_idx = np.where(sampled_sv_idx_list_sorted == bp_idx)[0][0]
            F_SV_info[new_idx][0] = chrom
            F_SV_info[new_idx][1] = pos
            F_SV_info[new_idx][2] = "sv_" + str(bp_idx)
        else:
            new_idx = np.where(unsampled_sv_idx_list_sorted == bp_idx)[0][0]
            F_SV_unsampled_info[new_idx][0] = chrom
            F_SV_unsampled_info[new_idx][1] = pos
            F_SV_unsampled_info[new_idx][2] = "sv_" + str(bp_idx)

    for (chrom, pos), snv_idx in SNV_idx_dict.items():
        if snv_idx in sampled_snv_idx_list_sorted:
            new_idx = np.where(sampled_snv_idx_list_sorted == snv_idx)[0][0]
            F_SNV_info[new_idx][0] = chrom
            F_SNV_info[new_idx][1] = pos
            F_SNV_info[new_idx][2] = "snv_" + str(snv_idx)
        else:
            new_idx = np.where(unsampled_snv_idx_list_sorted == snv_idx)[0][0]
            F_SNV_unsampled_info[new_idx][0] = chrom
            F_SNV_unsampled_info[new_idx][1] = pos
            F_SNV_unsampled_info[new_idx][2] = "snv_" + str(snv_idx)

    for (chrom, startpos), cn_idx in CN_startPos_dict.items():
        F_CNV_info[cn_idx][0] = chrom
        F_CNV_info[cn_idx][1] = startpos
        F_CNV_info[cn_idx][2] = "cnv" + str(cn_idx)
        F_CNV_info[cn_idx + r][0] = chrom
        F_CNV_info[cn_idx + r][1] = startpos
        F_CNV_info[cn_idx + r][2] = "cnv" + str(cn_idx)
    # for (chrom, endpos), cn_idx in CN_endPos_dict:
    #     assert(F_info_phasing[l+g+cn_idx][0] == chrom)
    #     F_info_phasing[l+g+cn_idx][2] = endpos
    #     assert (F_info_phasing[l + g + cn_idx+r][0] == chrom)
    #     F_info_phasing[l + g + cn_idx+r][2] = endpos
    # make list of segment boundaries. used to set Q to 1 even if bp not on edge of segment
    seg_dic = _get_seg_bgn_end_pos(CN_startPos_dict, CN_endPos_dict)

    for sample_idx in range(len(sampleList)):
        sample = sampleList[sample_idx]
        for chrom in BP_sample_dict[sample]:
            for pos in BP_sample_dict[sample][chrom]:
                for bp_id in BP_sample_dict[sample][chrom][pos]:
                    temp_bp_info_dict = BP_sample_dict[sample][chrom][pos][bp_id] # dictionary
                    # cn, direction, bdp, dp = temp_bp_info_dict['cn'], temp_bp_info_dict['dir'], temp_bp_info_dict['bdp'], temp_bp_info_dict['dp']
                    cn, direction, = temp_bp_info_dict['cn'], temp_bp_info_dict['dir']
                    bp_idx = BP_idx_dict[(chrom, pos, direction)]
                    if bp_idx in sampled_sv_idx_list_sorted:
                        new_idx = np.where(sampled_sv_idx_list_sorted == bp_idx)[0][0]
                        #F[sample_idx][bp_idx] = cn
                        F_SV[sample_idx][new_idx] = cn

                        # A[sample_idx][bp_idx] = bdp
                        # H[sample_idx][bp_idx] = dp

                        if direction == False and (chrom, pos) in CN_endPos_dict:
                            cn_idx = CN_endPos_dict[(chrom, pos)]
                            Q_SV[new_idx][cn_idx] = 1
                        elif direction == True and (chrom, pos) in CN_startPos_dict:
                            cn_idx = CN_startPos_dict[(chrom, pos)]
                            Q_SV[new_idx][cn_idx] = 1
                        else: # search through all posible segments where bp could lie
                            if chrom in seg_dic.keys():
                                cn_idx = _get_seg_idx(seg_dic[chrom], pos)
                                if cn_idx != None:
                                    Q_SV[new_idx][cn_idx] = 1
                                else:
                                    print("breakpoint id " + str(bp_id) + " at chr " + str(chrom) + " pos " + str(pos) + " is not found in copy number info.")
                            else:
                                print("breakpoint id " + str(bp_id) + " at chr " + str(chrom) + " pos " + str(
                                    pos) + " is not found in copy number info.")
                    else:
                        new_idx = np.where(unsampled_sv_idx_list_sorted == bp_idx)[0][0]
                    #F[sample_idx][bp_idx] = cn
                        F_SV_unsampled[sample_idx][new_idx] = cn

                        # A[sample_idx][bp_idx] = bdp
                        # H[sample_idx][bp_idx] = dp

                        if direction == False and (chrom, pos) in CN_endPos_dict:
                            cn_idx = CN_endPos_dict[(chrom, pos)]
                            Q_SV_unsampled[new_idx][cn_idx] = 1
                        elif direction == True and (chrom, pos) in CN_startPos_dict:
                            cn_idx = CN_startPos_dict[(chrom, pos)]
                            Q_SV_unsampled[new_idx][cn_idx] = 1
                        else: # search through all posible segments where bp could lie
                            if chrom in seg_dic.keys():
                                cn_idx = _get_seg_idx(seg_dic[chrom], pos)
                                if cn_idx != None:
                                    Q_SV_unsampled[new_idx][cn_idx] = 1
                                else:
                                    print("breakpoint id " + str(bp_id) + " at chr " + str(chrom) + " pos " + str(pos) + " is not found in copy number info.")
                            else:
                                print("breakpoint id " + str(bp_id) + " at chr " + str(chrom) + " pos " + str(
                                    pos) + " is not found in copy number info.")


        for chrom, pos in SNV_sample_dict[sample].keys():
            snv_idx = SNV_idx_dict[(chrom, pos)]
            cn = SNV_sample_dict[sample][(chrom, pos)]
            if snv_idx in sampled_snv_idx_list_sorted:
                new_idx = np.where(sampled_snv_idx_list_sorted == snv_idx)[0][0]
                F_SNV[sample_idx][new_idx] = cn
                if chrom in seg_dic.keys():
                    cn_idx = _get_seg_idx(seg_dic[chrom], pos)
                    if cn_idx != None:
                        Q_SNV[new_idx][cn_idx] = 1
                    else:
                        print("snv at chr " + str(chrom) + " pos " + str(
                            pos) + " is not found in copy number info.")
                else:
                    print("snv id at chr " + str(chrom) + " pos " + str(
                        pos) + " is not found in copy number info.")
            else:
                new_idx = np.where(unsampled_snv_idx_list_sorted == snv_idx)[0][0]
                F_SNV_unsampled[sample_idx][new_idx] = cn
                if chrom in seg_dic.keys():
                    cn_idx = _get_seg_idx(seg_dic[chrom], pos)
                    if cn_idx != None:
                        Q_SNV_unsampled[new_idx][cn_idx] = 1
                    else:
                        print("snv at chr " + str(chrom) + " pos " + str(
                            pos) + " is not found in copy number info.")
                else:
                    print("snv id at chr " + str(chrom) + " pos " + str(
                        pos) + " is not found in copy number info.")
        for chrom in CN_sample_rec_dict[sample]:
            for (s,e) in CN_sample_rec_dict[sample][chrom]:
                cn_idx_list = get_CN_indices(CN_startPos_dict, CN_endPos_dict, chrom, s, e)
                cn = CN_sample_rec_dict[sample][chrom][(s,e)]
                cn_minor = CN_sample_rec_dict_minor[sample][chrom][(s, e)]
                cn_major = CN_sample_rec_dict_major[sample][chrom][(s, e)]
                for cn_idx in cn_idx_list:
                    F_CNV[sample_idx][cn_idx] = cn_minor
                    F_CNV[sample_idx][cn_idx+r] = cn_major

    # create dictionary with key as segment index and val as tuple containing (chrm, bgn, end)
    cv_attr = { i: (chrm, bgn, end) for chrm, lst in seg_dic.iteritems() for (i, bgn, end) in lst }
    return F_phasing, F_unsampled_phasing, G_sampled, G_unsampled, Q, Q_unsampled, A, H, cv_attr, F_info_phasing, F_unsampled_info_phasing, sampled_snv_idx_list_sorted, unsampled_snv_idx_list_sorted, sampled_sv_idx_list_sorted, unsampled_sv_idx_list_sorted
    ### A and H are empty lists

#  input: segs (list of tuple) tuple is ( seg_idx, bgn_pos, end_pos ) for segments of a single chromosome
#         pos (int) position of segment that will be returned
# output: i (int) index of segment where pos lies
def _get_seg_idx(segs, pos):
    for idx, bgn, end in segs:
        if bgn <= pos and pos <= end:
            return idx
    return None


# output: seg_dic (dict) key is chrm (int). val is segs (list of tuple)
#                                           tuple is ( seg_idx, bgn_pos, end_pos ) of each segment
# (list of tuple) tuple is ( chrm, bgn_pos, end_pos ) for each segment
def _get_seg_bgn_end_pos(CN_startPos_dict, CN_endPos_dict):
    idx_to_bgn = _inv_dic(CN_startPos_dict)
    idx_to_end = _inv_dic(CN_endPos_dict)
    idxs = sorted(idx_to_bgn.keys())
    seg_dic = {}
    for i in idxs:
        chm, bgn = idx_to_bgn[i]

        _, end = idx_to_end[i]
        #print(i, chm, bgn, end)
        if chm not in seg_dic:
            seg_dic[chm] = []
        seg_dic[chm].append((i, bgn, end))
    return seg_dic

# inverts dictionary so keys become values, values become keys
def _inv_dic(dic):
    inv_dic = {}
    for k, v in dic.iteritems():
        inv_dic[v] = k
    return inv_dic

###xf: key -(chrom, pos) for snv, value - idx starting from 0
def get_snv_idx_dict(SNV_sample_dict):
    idx = 0
    SNV_idx_dict = {}
    chrom_pos_set = set()
    for sample in SNV_sample_dict.keys():
        for key in SNV_sample_dict[sample].keys():
            if key not in chrom_pos_set:
                chrom_pos_set.add(key)

    for key in sorted(list(chrom_pos_set), key=lambda x: (int(x[0]), x[1])):
        SNV_idx_dict[key] = idx
        idx += 1
    g = idx
    return SNV_idx_dict, g


# key: (chrom, pos, dir)
# val: idx (idx starts from 0)
def get_BP_idx_dict(BP_sample_dict):
    chrom_pos_dir_dict = dict() # key: chrom, val: set of (pos, dir) tuples

    for sample in BP_sample_dict:
        for chrom in BP_sample_dict[sample]:
            if chrom not in chrom_pos_dir_dict:
                chrom_pos_dir_dict[chrom] = set()
            for pos in BP_sample_dict[sample][chrom]:
                for bp_id in BP_sample_dict[sample][chrom][pos]:
                    direction = BP_sample_dict[sample][chrom][pos][bp_id]['dir']
                    chrom_pos_dir_dict[chrom].add((pos, direction))

    chrom_pos_dict = dict() # key: chrom, val: sorted pos list (ascending)
    for chrom in chrom_pos_dir_dict:
        sorted_pos_list = sorted(map(operator.itemgetter(0), chrom_pos_dir_dict[chrom]))
        chrom_pos_dict[chrom] = sorted_pos_list

    BP_patient_dict = dict()
    for chrom in chrom_pos_dict:
        BP_patient_dict[chrom] = list()
        for pos in chrom_pos_dict[chrom]:
            if (pos, False) in chrom_pos_dir_dict[chrom]:
                BP_patient_dict[chrom].append((pos, False))

            if (pos, True) in chrom_pos_dir_dict[chrom]:
                BP_patient_dict[chrom].append((pos, True))

    BP_idx_dict = dict()
    idx = 0
    sorted_chrom = sorted(BP_patient_dict.keys(),key=int)
    for chrom in sorted_chrom:
        for (pos, direction) in BP_patient_dict[chrom]:
            if (chrom, pos, direction) in BP_idx_dict:
                continue

            BP_idx_dict[(chrom, pos, direction)] = idx
            #print(idx, chrom, pos)
            idx += 1
    l = idx
    return BP_idx_dict, l

def _inv_dic(dic):
    inv_dic = {}
    for k, v in dic.iteritems():
        inv_dic[v] = k
    return inv_dic


# return three dictionaries: BP_sample_dict, CN_sample_dict, and CN_sample_rec_dict
# 1. BP_sample_dict: 
#    key: sample
#    val: {chr1:{ pos1:{dir: T/F, cn: , a: , h: }, pos2: {dir: , cn: , a:, h: }, chr2: {}, ...}
#    mate_dir = rec.ALT[0].remoteOrientation. if mate_dir == False: ], if mate_dir == True: [
# 2. CN_sample_dict:
#    key: sample
#    value: {chr1: {pos1: s/e, pos2: s/e, ...}, chr2: {}, ... }
# 3. CN_sample_rec_dict: 
#    key: sample
#    value: {chr1: {(s1, e1): cn1, (s2, e2): cn2, ...}, chr2: {...}...}
# 4. bp_id_to_mate_id (dict) key (str) is ID of breakpoint. val (str) is ID of mate
# 5. bp_id_to_tuple   (dict) key (str) is ID of breakpoint. val (tuple) is (chrm_num, pos, direction)
def get_sample_dict(reader, scrna_df):
    BP_sample_dict, CN_sample_dict, CN_sample_rec_dict_minor, CN_sample_rec_dict_major, CN_sample_rec_dict = dict(), dict(), dict(), dict(), dict()
    SNV_sample_dict = {}
    bp_id_to_mate_id = {} # key is id (str). val is mate id (str)
    bp_id_to_tuple = {}   # key is (chrm_num, pos, direction). key is id (str)
    bp_id_to_mate_dir = {}
    # bp_idx_dict, snv_idx_dict, cnv_idx_dict = {}, {}, {}
    # bp_idx = 0
    # cnv_idx = 0
    # snv_idx = 0
    # nishat added for scrna nov 29, 2024
    C_RNA = scrna_df.to_numpy()
    rna_cols = scrna_df.columns
    rna_cols = rna_cols[:len(rna_cols)//2]
    
    rna_col_df = pd.DataFrame(columns=['CHROM', 'st', 'end']) ### nb
    for i in rna_cols: ### nb
        rna_col_df = pd.concat([rna_col_df, pd.DataFrame({'CHROM': [int(i.split('_')[0])], 'st': [int(i.split('_')[1])], 'end': [int(i.split('_')[2])]})], ignore_index=True,sort = False) ### nb
    
    #----
    count = 0
    bp_id_set = set()
    for rec in reader:
        if is_sv_record(rec):
            count += 1
            #print(rec)
            if rec.CHROM not in BP_sample_dict:
                BP_sample_dict[rec.CHROM] = dict()
            if rec.POS not in BP_sample_dict[rec.CHROM]:
                BP_sample_dict[rec.CHROM][rec.POS] = dict()
            bp_id = rec.ID
            if bp_id not in bp_id_set:
                bp_id_set.add(bp_id)
            else:
                print(bp_id, 'already in set')
            #print bp_id
            if bp_id not in BP_sample_dict[rec.CHROM][rec.POS]: # had to add unique identifier since seg len of 1 exists
                BP_sample_dict[rec.CHROM][rec.POS][bp_id] = {}
            else:
                print(bp_id, 'already in set')
            BP_sample_dict[rec.CHROM][rec.POS][bp_id]['id'] = rec.ID
            BP_sample_dict[rec.CHROM][rec.POS][bp_id]['cn'] = rec.samples[0].data.CNADJ
            BP_sample_dict[rec.CHROM][rec.POS][bp_id]['mate_dir'] = rec.ALT[0].remoteOrientation
            # BP_sample_dict[rec.CHROM][rec.POS][bp_id]['mate_id'] = rec.INFO['MATEID']
            BP_sample_dict[rec.CHROM][rec.POS][bp_id]['mate_pos'] = rec.ALT[0].pos
            BP_sample_dict[rec.CHROM][rec.POS][bp_id]['mate_chr'] = rec.ALT[0].chr

            bp_id_to_mate_id[rec.ID] = rec.INFO['MATEID'][0]
            bp_id_to_mate_dir[rec.ID] = rec.ALT[0].remoteOrientation

            # BP_sample_dict[rec.CHROM][rec.POS]['bdp'] = rec.samples[0].data.BDP
            # BP_sample_dict[rec.CHROM][rec.POS]['dp'] = rec.samples[0].data.DP

        elif is_snv_record(rec):
            if (rec.CHROM, rec.POS) not in SNV_sample_dict:
                SNV_sample_dict[(rec.CHROM,rec.POS)] = rec.samples[0].data.CNADJ

        elif is_cnv_record(rec):
            if int(rec.CHROM) not in rna_col_df['CHROM']: ### nb
                continue ### nb
            else:  ### nb
                chr_subdf = rna_col_df[rna_col_df['CHROM']==int(rec.CHROM)] ### nb
                if isinstance(rec.INFO['END'], list): 
                    info_end = rec.INFO['END'][0]
                else:
                    info_end = rec.INFO['END']
                range_matches = chr_subdf.apply(lambda row: int(rec.POS) >= row['st'] and int(info_end) <= row['end'], axis=1) ### nb
                
                if not range_matches.empty and range_matches.any(): ### nb
                    
                    if rec.CHROM not in CN_sample_dict:
                        CN_sample_dict[rec.CHROM] = dict()
                        CN_sample_rec_dict[rec.CHROM] = dict() ### xf
                        CN_sample_rec_dict_minor[rec.CHROM] = dict() ### xf
                        CN_sample_rec_dict_major[rec.CHROM] = dict() ### xf
                    
                    CN_sample_dict[rec.CHROM][rec.POS] = ['s']
                    CN_sample_dict[rec.CHROM][info_end] = ['e']
                    CN_sample_rec_dict[rec.CHROM][(rec.POS, info_end)] = sum(rec.samples[0].data.CN)
                    CN_sample_rec_dict_minor[rec.CHROM][(rec.POS, info_end)] = rec.samples[0].data.CN[0]
                    CN_sample_rec_dict_major[rec.CHROM][(rec.POS, info_end)] = rec.samples[0].data.CN[1]
    count2 = 0
    for chrom in BP_sample_dict:
        for pos in BP_sample_dict[chrom]:
            for bp_id in BP_sample_dict[chrom][pos]:
                count2 += 1
                mate_chr = BP_sample_dict[chrom][pos][bp_id]['mate_chr']
                mate_pos = BP_sample_dict[chrom][pos][bp_id]['mate_pos']

                mate_id = bp_id_to_mate_id[bp_id]
                my_dir = bp_id_to_mate_dir[mate_id]
                BP_sample_dict[chrom][pos][bp_id]['dir'] = my_dir

                bp_id_to_tuple[bp_id] = (chrom, pos, my_dir)
    
    #### nb:: adding average of genes according to DNA segments.
    for chrom, segments in CN_sample_rec_dict.items():
        for cn_range, _ in segments.items():
            matching_indices = rna_col_df[
                (rna_col_df['CHROM'] == int(chrom)) &
                (rna_col_df['st'] >= cn_range[0]) &
                (rna_col_df['end'] <= cn_range[1])
            ].index
            
            if not matching_indices.empty:
                if len(matching_indices > 1):
                    no_genes = rna_col_df.shape[0]
                    matching_indices_minor = matching_indices + no_genes
                    avg = np.round(C_RNA[:, matching_indices].mean(axis=1), decimals=2)
                    avg_minor = np.round(C_RNA[:, matching_indices_minor].mean(axis=1), decimals=2)
                    first_index_major = matching_indices[0]
                    first_index_minor = matching_indices_minor[0]
                    C_RNA[:, first_index_major] = avg
                    C_RNA[:, first_index_minor] = avg_minor
                    
                    rna_col_df.loc[first_index_major, 'st'] = cn_range[0]
                    rna_col_df.loc[first_index_major, 'end'] = cn_range[1]

                    indices_to_drop_major = matching_indices[1:]
                    indices_to_drop_minor = matching_indices_minor[1:]

                    indices_to_drop = np.append(indices_to_drop_major, indices_to_drop_minor)
                    rna_col_df = rna_col_df.drop(indices_to_drop_major).reset_index(drop=True)
                    C_RNA = np.delete(C_RNA, indices_to_drop, axis=1)
    
    return BP_sample_dict, CN_sample_dict, CN_sample_rec_dict, CN_sample_rec_dict_minor, CN_sample_rec_dict_major, bp_id_to_mate_id, bp_id_to_tuple, SNV_sample_dict, C_RNA


# CN_startPos_dict: key: (chrom, startPos), val: idx
# CN_endPos_dict: key: (chrom, endPos), val: idx
def get_CN_indices_dict(CN_sample_dict):

    chrom_dict = dict() # key: chrom, value: list of samples contain this chrom
    for sample in CN_sample_dict:
        for chrom in CN_sample_dict[sample]:
            if chrom not in chrom_dict:
                chrom_dict[chrom] = list()
            chrom_dict[chrom].append(sample)

    CN_patient_dict = dict()
    for chrom in chrom_dict:
        posSet = set()
        pos_dir_dict = dict() # given pos, output ['e'] or ['s'] or ['s', 'e']
        for sample in chrom_dict[chrom]:
            for pos in CN_sample_dict[sample][chrom]:
                posSet.add(pos)
                if pos not in pos_dir_dict:
                    pos_dir_dict[pos] = CN_sample_dict[sample][chrom][pos]
                else:
                    if CN_sample_dict[sample][chrom][pos] != pos_dir_dict[pos]:
                        pos_dir_dict[pos] += CN_sample_dict[sample][chrom][pos]
        posList = sorted(list(posSet), key=int)

        CN_patient_dict[chrom] = list()
        tempS = posList[0]
        idx = 0
        while idx < len(posList) - 1:
            if 'e' in pos_dir_dict[posList[idx]]:
                tempE = posList[idx]
                CN_patient_dict[chrom].append((tempS, tempE))
                if 's' in  pos_dir_dict[posList[idx+1]]:
                    tempS = posList[idx + 1]
                else:
                    tempS = posList[idx] + 1
                idx += 1
            else:
                if 's' in pos_dir_dict[posList[idx + 1]] and 'e' not in pos_dir_dict[posList[idx + 1]]:
                    tempE = posList[idx + 1] - 1
                    CN_patient_dict[chrom].append((tempS, tempE))
                    tempS = posList[idx + 1]
                    idx += 1
                elif 'e' in pos_dir_dict[posList[idx + 1]] and 's' not in pos_dir_dict[posList[idx + 1]]:
                    tempE = tempE = posList[idx + 1]
                    CN_patient_dict[chrom].append((tempS, tempE))
                    if idx + 1 < len(posList) - 1:
                        tempS = posList[idx + 2]
                    idx += 2
                elif 's' in pos_dir_dict[posList[idx + 1]] and 'e' in pos_dir_dict[posList[idx + 1]]:
                    tempE = posList[idx + 1] - 1
                    CN_patient_dict[chrom].append((tempS, tempE))
                    CN_patient_dict[chrom].append((posList[idx + 1], posList[idx + 1]))
                    tempS = posList[idx + 1] + 1
                    idx += 1

    CN_startPos_dict = dict()
    CN_endPos_dict = dict()
    idx = 0
    sorted_chrom = sorted(CN_patient_dict.keys(), key=int)
    for chrom in sorted_chrom:
        for (s,e) in CN_patient_dict[chrom]:
            CN_startPos_dict[(chrom, s)] = idx
            CN_endPos_dict[(chrom, e)] = idx
            #print(idx, chrom, s, e)
            idx += 1
    r = idx
    return CN_startPos_dict, CN_endPos_dict, r


#  input: bp_tuple_to_idx (dict) key is bp tuple (chrm, pos, direction). val is index of output G
#         bp_id_to_mate_id (dict) key (str) is ID of breakpoint. val (str) is ID of mate
#         bp_id_to_tuple   (dict) key (str) is ID of breakpoint. val (tuple) is (chrm_num, pos, direction)
# output: G (np.array of 0 or 1) [l, l] g_s,t == 1 if breakpoints s and t are mates. 0 otherwise
def make_G(bp_tuple_to_idx, bp_id_to_mate_id, bp_id_to_tuple):
    l = len(bp_tuple_to_idx.keys())
    G = np.zeros((l, l))

    for i in xrange(0, l):
        G[i, i] = 1          # breakpoint being its own mate is a requirement for the solver

    bp_idx_to_tuple = inv_dict(bp_tuple_to_idx)
    bp_tuple_to_mate_tuple = get_bp_tuple_to_mate_tuple(bp_id_to_mate_id, bp_id_to_tuple)

    for i in sorted(bp_idx_to_tuple.iterkeys()):
        cur_tuple = bp_idx_to_tuple[i]
        mate_tup = bp_tuple_to_mate_tuple[cur_tuple]
        j = bp_tuple_to_idx[mate_tup]
        G[i, j] = 1

    return G

#  input: bp_id_to_mate_id (dict) key (str) is ID of breakpoint. val (str) is ID of mate
#         bp_id_to_tuple   (dict) key (str) is ID of breakpoint. val (tuple) is (chrm_num, pos, direction)
# output: bp_tuple_to_mate_tuple (dict) key is (tuple) is (chrm_num, pos, direction). val is mate tuple
def get_bp_tuple_to_mate_tuple(bp_id_to_mate_id, bp_id_to_tuple):
    out_dic = {}
    bp_tuple_to_id = inv_dict(bp_id_to_tuple)
    for tup, cur_id in bp_tuple_to_id.iteritems():
        mate_id = bp_id_to_mate_id[cur_id]
        mate_tup = bp_id_to_tuple[mate_id]
        out_dic[tup] = mate_tup
    return out_dic

# inverts dictionary. keys become values. values become keys. must be able to be inverted so
#   input keys must be static
def inv_dict(dic):
    idic = {}
    for k, v in dic.iteritems():
        idic[v] = k
    return idic


# given start and end position, output list of segment indices (continuous)
def get_CN_indices(CN_startPos_dict, CN_endPos_dict, chrom, s, e):
    result = list()
    firstIdx = CN_startPos_dict[(chrom,s)]
    endIdx = CN_endPos_dict[(chrom, e)]
    for i in range(firstIdx, endIdx + 1):
        result.append(i)
    return result


def is_cnv_record(rec):
    return rec.ID[0:3] == 'cnv'


def is_sv_record(rec):
    return rec.ID[0:2] == 'sv'


def is_snv_record(rec):
    return rec.ID[0:3] == 'snv'
