#   author: Jesse Eaton and Xuecong Fu
#   the file is originated from solver.py in TUSV by Jesse Eaton. Xuecong Fu fixed bugs and extended it to current model TUSV-ext.


# # # # # # # # # # #
#   I M P O R T S   #
# # # # # # # # # # #

import sys  
import os  
import argparse  
import math  
import numpy as np
import gurobipy as gp

# # # # # # # # # # # # #
#   C O N S T A N T S   #
# # # # # # # # # # # # #

U_MIN = 0.0
MAX_SOLVER_ITERS = 5000


# # # # # # # # # # # # #
#   F U N C T I O N S   #
# # # # # # # # # # # # #

#  input: F (np.array of float) [m, l+g+2r] mixed copy number f_p,s of mutation s in sample p
#         Q (np.array of 0 or 1) [l+g, r] q_b,s == 1 if breakpoint b is in segment s. 0 otherwise
#         G (np.array of 0 or 1) [l, l] g_s,t == 1 if breakpoints s and t are mates. 0 otherwise
#         A (np.array of int) [m, l] a_p,b is number of mated reads for breakpoint b in sample p
#         H (np.array of int) [m, l] h_p,b is number of total reads for breakpoint b in sample p
#         n (int) number of leaves in phylogeny. 2n-1 is total number of nodes
#         c_max (int) maximum allowed copy number for any element in output C
#         lamb1 (float) regularization term to weight total tree cost against unmixing error
#         lamb2 (float) regularization term to weight breakpoint frequency error
#         max_iters (int) maximum number of iterations to predict U then C if convergence not reached
#         time_limit (int) maximum number of seconds the solver will run
#         only_leaf (boolean) the flag indicating the if the model assumes that samples are unmixed by only leaf node clones, default is False.
# output: U (np.array of float) [m, 2n-1] 0 <= u_p,k <= 1. percent of sample p made by clone k
#         C (np.array of int) [2n-1, l+g+2r] int copy number c_k,s of mutation s in clone k
#         E (np.array of int) [2n-1, 2n-1] e_i,j == 1 iff edge (i,j) is in tree. 0 otherwise
#         R (np.array of int) [2n-1, 2n-1] cost of each edge in the tree
#         W_all (np.array of int) [2n-1, 2n-1] number of breakpoints appearing along each edge in tree
#         obj_val (float) objective value of final solution
#         err_msg (None or str) None if no error occurs. str with error message if one does
#  notes: l (int) is number of breakpoints depicting structural variants. r (int) is number of copy number regions, 2r means we phase it for allelic copy numbers,
#         g (int) is number of single nucleotide variants.

def get_UCE(F_phasing, C_RNA, Q, G, A, H, n, c_max, lamb1, lamb2, max_iters, time_limit=None, only_leaf=False):
    np.random.seed()  # sets seed for running on multiple processors
    m = len(F_phasing)
    l_g_sample, r = Q.shape
    l,_ = G.shape
    g = l_g_sample - l
    for i in xrange(0, max_iters):

        if i == 0:
            U = gen_U(m, n)
        else:
            U = get_U(F_phasing, C, n, l, only_leaf)
        obj_val, M, C, E, A, R, W, W_sv, W_snv, err_msg = get_C(F_phasing, C_RNA, U, Q, G, A, H, n, c_max, lamb1, lamb2, time_limit)

        # handle errors
        if err_msg != None:
            return None, None, None, None, None, None, err_msg

        if i > 0:
            if abs((C - prevC)).sum() == 0:
                break

        prevC = C

    return U, M, C, E, A, R, W, W_sv, W_snv, obj_val, None


#  input: F (np.array of float) [m, l+g+2r] mixed copy number f_p,s of mutation s in sample p
#         C (np.array of int) [2n-1, l+g+2r] int copy number c_k,s of mutation s in clone k
#         n (int) number of leaves in phylogeny. 2n-1 is total number of nodes
# output: U (np.array of float) [m, 2n-1] 0 <= u_p,k <= 1. percent of sample p made by clone k
def get_U(F_phasing, C, n, l, only_leaf):
    m, L = F_phasing.shape  ### xf: L=l(+g)+2r depending on if SNVs are included
    N = 2 * n - 1
    
    mod = gp.Model('tusv')
    U = _get_gp_arr_cnt_var(mod, m, N, 1.0)
    for i in xrange(0, m):
        mod.addConstr(gp.quicksum(U[i, :]) == 1.0, "Frequencies sum equals to 1")
        if only_leaf:
            mod.addConstr(gp.quicksum(U[i, n: -1]) == 0.0, "Internal nodes have zero frequencies")
    sums = []
    
    for p in xrange(0, m):
        for s in xrange(0, L):
            f_hat = gp.quicksum([U[p, k] * C[k, s] for k in xrange(0, N)])  ### xf: Now U remains m*N, C becomes N*(l(+g)+2r), F is m*(l(+g)+2r)
           
            sums.append(_get_abs(mod, F_phasing[p, s] - f_hat))
            #sums.append(F_phasing[p, s] * f_hat)
    mod.setObjective(gp.quicksum(sums), gp.GRB.MINIMIZE)
    #mod.setObjective(gp.quicksum(sums), gp.GRB.MAXIMIZE)
    
    '''
    
    mean_F = gp.quicksum(F_phasing[p, s] for p in xrange(0, m) for s in xrange(0, L)) / (m * L)
    mean_UC = gp.quicksum(U[p, k] * C[k, s] for p in xrange(0, m) for k in xrange(0, N) for s in xrange(0, L)) / (m * L)

    sums = []
    for p in xrange(0, m):
        for s in xrange(0, L):
            f_hat = gp.quicksum([U[p, k] * C[k, s] for k in xrange(0, N)])  # UC[p, s]
            sums.append((F_phasing[p, s] - mean_F) * (f_hat - mean_UC))
    reg_term = gp.quicksum(U[p, k] * U[p, k] for p in xrange(0, m) for k in xrange(0, N))
    mod.setObjective(gp.quicksum(sums) - 0.25 * reg_term, gp.GRB.MAXIMIZE)
    '''
    mod.optimize()
    U = _as_solved(U)

    for i in xrange(m):
        for j in xrange(2 * n - 1):
            if U[i, j] <= U_MIN:
                U[i, j] = 0.0

    # renormalize U so all rows sum to 1
    rowsums = np.sum(U, 1)
    for i in xrange(m):
        U[i, :] = U[i, :] / rowsums[i]

    return U


#  input: F (np.array of float) [m, l+g+2r] mixed copy number f_p,s of mutation s in sample p
#         U (np.array of float) [m, 2n-1] 0 <= u_p,k <= 1. percent of sample p made by clone k
#         Q (np.array of 0 or 1) [l+g, r] q_b,s == 1 if breakpoint b is in segment s. 0 otherwise
#         G (np.array of 0 or 1) [l, l] g_s,t == 1 if breakpoints s and t are mates. 0 otherwise
#         A (np.array of int) [m, l] a_p,b is number of mated reads for breakpoint b in sample p
#         H (np.array of int) [m, l] h_p,b is number of total reads for breakpoint b in sample p
#         n (int) number of leaves in phylogeny. 2n-1 is total number of nodes
#         c_max (int) maximum allowed copy number for any element in output C
#         lamb1 (float) regularization term to weight total tree cost against unmixing error
#         lamb2 (float) regularization term to weight breakpoint frequency error
#         time_limit (int) maximum number of seconds the solver will run
# output: obj_val (float) objective value of solution
#         C (np.array of int) [2n-1, l+g+2r] int copy number c_k,s of mutation s in clone k
#         E (np.array of int) [2n-1, 2n-1] e_i,j == 1 iff edge (i,j) is in tree. 0 otherwise
#         R (np.array of int) [2n-1, 2n-1] cost of each edge in the tree
#         W_all (np.array of int) [2n-1, 2n-1] number of breakpoints appearing along each edge in tree
#         err_msg (None or str) None if no error occurs. str with error message if one does
#  notes: l (int) is number of breakpoints. g (int) is the number of single nucleotide variants. r (int) is number of copy number regions
def get_C(F_phasing, C_RNA, U, Q, G, A, H, n, c_max, lamb1, lamb2, time_limit=None):
    l_g, r = Q.shape
    #print("r shape",r)
    l, _ = G.shape
    g = l_g - l
    m, _ = U.shape
    N = 2 * n - 1
    mod = gp.Model('tusv')

    C = _get_gp_arr_int_var(mod, N, l + g + 2*r, c_max)  ### xf: C becomes N*(l+2r) ### nb: commented
    #C_lg = _get_gp_arr_int_var(mod, N, l + g, c_max)
    M = _get_gp_arr_bin_var(mod, N, N) # nb: num_nodes * num_clones
    #C_2r = np.dot(M, C_RNA) ### nb
    #C = np.concatenate((C_lg, C_2r), axis=1) ### nb
    E = _get_gp_arr_bin_var(mod, N, N)
    A = _get_gp_arr_bin_var(mod, N, N)  # ancestry matrix
    R = _get_gp_arr_int_var(mod, N, N, c_max * 2*r)  # rho. cost across each edge ### xf: R also doubles because there is a cost for both alleles
    S = _get_gp_arr_cnt_var(mod, m, l+g, c_max)  # ess. bpf penalty for each bp in each sample
    W = _get_gp_3D_arr_bin_var(mod, N, N, l+g)
    D = _get_gp_1D_arr_bin_var(mod, l+g)
    C_bin = _get_bin_rep(mod, C, c_max)
    Gam = _get_gp_3D_arr_int_var(mod, N, l+g, 2, c_max)

    F_seg = (F_phasing[:, l_g:-r] + F_phasing[:, -r:]).dot(np.transpose(Q))  # [m, l] mixed copy number of segment containing breakpoint
    Pi = np_divide_0(F_phasing[:, :l_g], F_seg)  # [m, l] expected bpf (ratio of bp copy num to segment copy num)

    _set_matching_constraints(mod, M)
    _set_copy_num_constraints(mod, C, n, l, g, r)
    _set_tree_constraints(mod, E, n)
    _set_ancestry_constraints(mod, A, E, N)
    _set_cost_constraints(mod, R, C, E, n, l, g, r, c_max)
    _set_bp_gain_and_loss_constraints(mod, C_bin, C, W, E, G, n, l, g, Gam, c_max, D)
    _set_segment_copy_num_constraints(mod, Gam, C, Q, W, m, n, l, g, r, D, c_max)
    _set_bpf_penalty(mod, S, Pi, U, C, Gam)

    mod.setObjective(_get_objective(mod, F_phasing, U, M, C,C_RNA, R, S, lamb1, lamb2, l_g), gp.GRB.MINIMIZE)

    mod.params.MIPFocus = 1
    if time_limit != None:
        mod.params.TimeLimit = time_limit

    mod.optimize()
    
    C = _as_solved(C)
    #C_lg = _as_solved(C_lg) ### nb
    M = _as_solved(M) ### nb
    ##C_2r = np.dot(M, C_RNA) ### nb
    #C = np.concatenate((C_lg, C_2r), axis=1) ### nb
    E = _as_solved(E)
    R = _as_solved(R)
    A = _as_solved(A)
    W_node_sv = np.zeros((N, l), dtype=int)
    W_node_snv = np.zeros((N, g), dtype=int)
    W_node = np.zeros((N, l+g), dtype=int)
    for j in xrange(0, N):
        for b in xrange(0, l):
            W_node_sv[j, b] = sum([int(W[i, j, b].X) for i in xrange(0, N)])
        for b in xrange(0, g):
            W_node_snv[j, b] = sum([int(W[i, j, l+b].X) for i in xrange(0, N)])
        for b in xrange(0, l+g):
            W_node[j, b] = sum([int(W[i, j, b].X) for i in xrange(0, N)])
    return mod.objVal, M, C, E, A, R, W_node, W_node_sv, W_node_snv, None



# # # # # # # # # # # # # # # # # # # # # #
#   G U R O B I   C O N S T R A I N T S   #
# # # # # # # # # # # # # # # # # # # # # #

def _set_matching_constraints(mod, M):
    # nb: as we are setting the C_RNA matrix as C, its rows will not follow our assumed tree structure. 
    # M matrix is a one-to-one mapping matrix from the nodes to the RNA clones in C_RNA. 
    # M * C will ensure the row ordering. 
    N = M.shape[0]
    for i in xrange(0, N):
        mod.addConstr(sum(M[i,j] for j in range(N)) == 1)
    for i in xrange(0, N):
        mod.addConstr(sum(M[j,i] for j in range(N)) == 1)
    
    

def _set_copy_num_constraints(mod, C, n, l, g, r):
    for b in xrange(0, l + g):
        mod.addConstr(C[2 * n - 2, b], gp.GRB.EQUAL, 0)  # bp has copy number 0 at root
    for s in xrange(l + g, l + g + 2*r): 
        mod.addConstr(C[2 * n - 2, s], gp.GRB.EQUAL, 1)  # seg has copy number 2 at root  ### xf: after phasing, both alleles have 1 copy # nb


def _set_tree_constraints(mod, E, n):
    N = 2 * n - 1
    for i in xrange(0, n):
        for j in xrange(0, N):
            mod.addConstr(E[i, j] == 0)  # no outgoing edges from leaves
    for i in xrange(n, N):
        mod.addConstr(E[i, N - 1] == 0)  # no edges from descendents to root
    for i in xrange(n, N - 1):
        mod.addConstr(E[i, i] == 0)  # no self edges. leaf and root already constrained
    for i in xrange(n, N):
        mod.addConstr(gp.quicksum(E[i, :]) == 2)  # internal nodes have 2 outgoing edges
    for j in xrange(0, N - 1):
        mod.addConstr(gp.quicksum(E[n:, j]) == 1)  # non root nodes have 1 incoming edge
    for i in xrange(n, N):
        for j in xrange(n, N):
            mod.addConstr(E[i, j] + E[j, i] <= 1)  # no 2 node cycles


def _set_ancestry_constraints(mod, A, E, N):
    for j in xrange(0, N - 1):
        mod.addConstr(A[N - 1, j] == 1)  # root v_{N-1} is ancestor to all nodes
    for i in xrange(0, N):
        mod.addConstr(A[i, N - 1] == 0)  # root v_{N-1} has no ancestors
    for i in xrange(0, N):
        for j in xrange(0, N):
            mod.addConstr(A[i, j] >= E[i, j])  # ancestor if parent
            for g in xrange(0, N):
                if g != i:
                    mod.addConstr(A[g, j] >= E[i, j] + A[g, i] - 1)  # v_j gets v_i's ancestor profile except a_{i,j}
                    mod.addConstr(A[g, j] <= 1 - E[i, j] + A[g, i])
    for i in xrange(0, N):
        for j in xrange(0, N):
            mod.addConstr(A[i, j] + A[j, i] <= 1)
    for i in xrange(0, N):
        mod.addConstr(A[i, i] == 0)

def _set_cost_constraints(mod, R, C, E, n, l, g, r, c_max):
    N = 2 * n - 1
    X1 = _get_gp_3D_arr_int_var(mod, N, N, r, c_max)
    X2 = _get_gp_3D_arr_int_var(mod, N, N, r, c_max)
    for i in xrange(0, N):
        for j in xrange(0, N):  # no cost if no edge exists
            for s in xrange(0, r):  # cost is difference between copy number  ### xf: change the copy numbers
                mod.addConstr(X1[i, j, s] <= c_max * E[i, j])
                mod.addConstr(X1[i, j, s] >= C[i, s + l + g] - C[j, s + l + g] - (c_max + 1) * (1 - E[i, j]))
                mod.addConstr(X1[i, j, s] >= -1 * (C[i, s + l + g] - C[j, s + l + g]) - (c_max + 1) * (1 - E[i, j]))
                mod.addConstr(X2[i, j, s] <= c_max * E[i, j])
                mod.addConstr(X2[i, j, s] >= C[i, s + l + g + r] - C[j, s + l + g + r] - (c_max + 1) * (1 - E[i, j]))
                mod.addConstr(X2[i, j, s] >= -1 * (C[i, s + l + g + r] - C[j, s + l + g + r]) - (c_max + 1) * (1 - E[i, j]))
            mod.addConstr(R[i, j] == (gp.quicksum(X1[i, j, :]) + gp.quicksum(X2[i, j, :])))


### xf: improve the constraints for SV related to CNV, replace the set_bp_appearance_constraints in add_phasing
def _set_bp_gain_and_loss_constraints(mod, C_bin, C, W, E, G, n, l, g, Gam, c_max, D):
    N = 2 * n - 1
    X = _get_gp_3D_arr_int_var(mod, N, N, l+g, 3)
    for i in xrange(0, N):
        for j in xrange(0, N):
            for b in xrange(0, l+g):  # only 0 if copy num goes from 0 to 1 across edge (i,j)
                mod.addConstr(X[i, j, b] == 2 + C_bin[i, b] - C_bin[j, b] - E[i, j])
    X_bin = _get_3D_bin_rep(mod, X, 3)
    for i in xrange(0, N):
        for j in xrange(0, N):
            for b in xrange(0, l+g):  # set W as bp appearance
                mod.addConstr(W[i, j, b] == 1 - X_bin[i, j, b])
            for s in xrange(0, l):
                for t in xrange(0, l):  # breakpoint pairs appear on same edge, not include SNVs
                    mod.addConstr(W[i, j, s] - W[i, j, t] <= 1 - G[s, t])
                    mod.addConstr(W[i, j, s] - W[i, j, t] >= - 1 + G[s, t])
    for b in xrange(0, l+g):  # breakpoints only appear once in the tree
        mod.addConstr(gp.quicksum([W[i, j, b] for i in xrange(0, N) for j in xrange(0, N)]) == 1)
    for i in xrange(0, N):
        for j in xrange(0, N):
            for b in xrange(0, l+g): ### xf: only set constraints to the breakpoints that are not appeared in this branch

                mod.addConstr(Gam[j, b, 0] - Gam[i, b, 0] >= C[j, b] - C[i, b] - (2 - E[i, j] - D[b] + W[i, j, b]) * (2 * c_max + 1))
                mod.addConstr(Gam[j, b, 0] - Gam[i, b, 0] <= C[j, b] - C[i, b] + (2 - E[i, j] - D[b] + W[i, j, b]) * (2 * c_max + 2))
                mod.addConstr(Gam[j, b, 1] - Gam[i, b, 1] >= C[j, b] - C[i, b] - (1 - E[i, j] + D[b] + W[i, j, b]) * (2 * c_max + 1))
                mod.addConstr(Gam[j, b, 1] - Gam[i, b, 1] <= C[j, b] - C[i, b] + (1 - E[i, j] + D[b] + W[i, j, b]) * (2 * c_max + 2))
                
### xf: _set_ancestry_condition_constraints removed 

def _set_segment_copy_num_constraints(mod, Gam, C, Q, W, m, n, l, g, r, D, c_max):
    N = 2 * n - 1
    for k in xrange(0, N):
        for b in xrange(0, l+g):  # define copy num of segment containing breakpoint
            mod.addConstr(Gam[k, b, 0] == gp.quicksum([Q[b, s] * C[k, l + g + s] for s in xrange(0, r)])) ### xf: change to new Gamma and C matrix
            mod.addConstr(Gam[k, b, 1] == gp.quicksum([Q[b, s] * C[k, l + g + s + r] for s in xrange(0, r)]))
            mod.addConstr(C[k, b] <= Gam[k, b, 0] + (1 - D[b]) * c_max)  # cp num breakpoint cant exceed cp num of seg containing bp
            mod.addConstr(C[k, b] <= Gam[k, b, 1] + D[b] * c_max)
    for j in xrange(0, N):
        for b in xrange(0, l+g):  # copy number of segment containing bp must be at least 1 if bp appears at node j
            mod.addConstr(Gam[j, b, 0] + 1 - D[b] >= gp.quicksum([W[i, j, b] for i in xrange(0, N)]))
            mod.addConstr(Gam[j, b, 1] + D[b] >= gp.quicksum([W[i, j, b] for i in xrange(0, N)]))


def _set_bpf_penalty(mod, S, Pi, U, C, Gam):
    m, l_g = S.shape
    N, _, _ = Gam.shape
    for p in xrange(0, m):
        for b in xrange(0, l_g):
            sg_cpnum_est = gp.quicksum([U[p, k] * (Gam[k, b, 0] + Gam[k, b, 1]) for k in xrange(0, N)])
            bp_cpnum_est = gp.quicksum([U[p, k] * C[k, b] for k in xrange(0, N)])
            mod.addConstr(S[p, b] == _get_abs(mod, Pi[p, b] * sg_cpnum_est - bp_cpnum_est))

# # # # # # # # #
#   OBJECTIVE   #
# # # # # # # # #

def _get_objective(mod, F_phasing, U,M, C,C_RNA, R, S, lamb1, lamb2, l_g):  # returns expression for objective
    m, L = F_phasing.shape
    N, _ = C.shape
    _, l = S.shape
    r = C_RNA.shape[1]
    sums = []
    for p in xrange(0, m):
        for s in xrange(0, L):
            f_hat = gp.quicksum([U[p, k] * C[k, s] for k in xrange(0, N)])
            sums.append(_get_abs(mod, F_phasing[p, s] - f_hat))
    for i in xrange(0, N):
        for j in xrange(0, N):
            sums.append(lamb1 * R[i, j])
    for p in xrange(0, m):
        for b in xrange(0, l):
            sums.append(lamb2 * S[p, b])
    
    # nb: scRNA matching objective sum
    for i in xrange(0, N):
        for j in xrange(0, r):
            c_hat = gp.quicksum([M[i, k] * C_RNA[k, j] for k in xrange(0, N)])
            sums.append(_get_abs(mod, C[i, l_g+j] - c_hat))
    mod.update()
    return gp.quicksum(sums)


def _calculate_objective(F, F_phasing, U, C, R, S, lamb1, lamb2):  # returns expression for objective
    m, L = F_phasing.shape
    N, _ = C.shape
    _, l = S.shape
    sums = []
    for p in xrange(0, m):
        for s in xrange(0, L):
            f_hat = np.sum([U[p, k] * C[k, s] for k in xrange(0, N)])
            sums.append(np.abs(F_phasing[p, s] - f_hat))
    for i in xrange(0, N):
        for j in xrange(0, N):
            sums.append(lamb1 * R[i, j])
    for p in xrange(0, m):
        for b in xrange(0, l):
            sums.append(lamb2 * S[p, b])
    return np.sum(sums)


def _calculate_S(S, Pi, U, C, Gam):
    m, l = S.shape
    N, _, _ = Gam.shape
    for p in xrange(0, m):
        for b in xrange(0, l):
            sg_cpnum_est = np.sum([U[p, k] * (Gam[k, b, 0] + Gam[k, b, 1]) for k in xrange(0, N)])
            bp_cpnum_est = np.sum([U[p, k] * C[k, b] for k in xrange(0, N)])
            mod.addConstr(S[p, b] == _get_abs(mod, Pi[p, b] * sg_cpnum_est - bp_cpnum_est))

# # # # # # # # # # # # # # # # # # # # # # # # # #
#   G U R O B I   V A R I A B L E   M A K E R S   #
# # # # # # # # # # # # # # # # # # # # # # # # # #

def _get_gp_arr_int_var(mod, m, n, vmax=None):
    X = np.empty((m, n), dtype=gp.Var)
    for i in xrange(0, m):
        for j in xrange(0, n):
            if vmax == None:
                X[i, j] = mod.addVar(lb=0, vtype=gp.GRB.INTEGER)
            else:
                X[i, j] = mod.addVar(lb=0, ub=vmax, vtype=gp.GRB.INTEGER)
    # mod.update()
    return X


def _get_gp_1D_arr_bin_var(mod, m):
    X = np.empty((m), dtype=gp.Var)
    for i in xrange(0, m):
        X[i] = mod.addVar(vtype=gp.GRB.BINARY)
    # mod.update()
    return X


def _get_gp_arr_bin_var(mod, m, n):
    X = np.empty((m, n), dtype=gp.Var)
    for i in xrange(0, m):
        for j in xrange(0, n):
            X[i, j] = mod.addVar(vtype=gp.GRB.BINARY)
    # mod.update()
    return X


def _get_gp_arr_cnt_var(mod, m, n, vmax=None):
    X = np.empty((m, n), dtype=gp.Var)
    for i in xrange(0, m):
        for j in xrange(0, n):
            if vmax == None:
                X[i, j] = mod.addVar(lb=0, vtype=gp.GRB.CONTINUOUS)
            else:
                X[i, j] = mod.addVar(lb=0, ub=vmax, vtype=gp.GRB.CONTINUOUS)
    # mod.update()
    return X


def _get_gp_3D_arr_int_var(mod, l, m, n, vmax):
    X = np.empty((l, m, n), dtype=gp.Var)
    for i in xrange(0, l):
        for j in xrange(0, m):
            for k in xrange(0, n):
                if vmax == None:
                    X[i, j, k] = mod.addVar(lb=0, vtype=gp.GRB.INTEGER)
                else:
                    X[i, j, k] = mod.addVar(lb=0, ub=vmax, vtype=gp.GRB.INTEGER)
    # mod.update()
    return X


def _get_gp_3D_arr_bin_var(mod, l, m, n):
    X = np.empty((l, m, n), dtype=gp.Var)
    for i in xrange(0, l):
        for j in xrange(0, m):
            for k in xrange(0, n):
                X[i, j, k] = mod.addVar(vtype=gp.GRB.BINARY)
    # mod.update()
    return X


def _get_abs(mod, x):
    x_abs = mod.addVar(vtype=gp.GRB.CONTINUOUS)
    # mod.update() # <- removing this drastically speeds up solver
    #mod.addConstr(x_abs == gp.abs_(x))
    mod.addConstr(x_abs, gp.GRB.GREATER_EQUAL, x)
    mod.addConstr(x_abs, gp.GRB.GREATER_EQUAL, -1 * x)
    return x_abs


def _get_sgn(mod, x, lb, ub): ###xf: when b=0, x<=0, when b=1, x>=1
    b = mod.addVar(vtype=gp.GRB.BINARY)
    mod.addConstr(lb * (1-b) <= x)
    mod.addConstr(x <= ub * b)
    return b


def _get_consensus_sgn(mod, x1, x2, lb, ub):
    con = mod.addVar(vtype=gp.GRB.INTEGER)
    #mod.addConstr(_get_sgn(mod, x1, lb, ub) == _get_sgn(mod, x2, lb, ub))
    mod.addConstr(con == _get_sgn(mod, x1, lb, ub) + _get_sgn(mod, x2, lb, ub))
    return con


def _get_bin_rep(mod, X, vmax):
    m, n = X.shape
    Y = _get_gp_arr_bin_var(mod, m, n)  # Y = 0 if X == 0. Y = 1 if X != 0
    num_bits = int(math.floor(math.log(vmax, 2))) + 1  # maximum number of bits required
    Z = _get_gp_3D_arr_bin_var(mod, m, n, num_bits)  # bit representation of X
    for i in xrange(0, m):
        for j in xrange(0, n):  # set Z as bit representation
            mod.addConstr(gp.quicksum([Z[i, j, b] * 2 ** b for b in xrange(0, num_bits)]) == X[i, j])
            for b in xrange(0, num_bits):  # Y must be 1 if any bits are 1
                mod.addConstr(Z[i, j, b] <= Y[i, j])  # Y must be 0 if all bits are 0
            mod.addConstr(Y[i, j] <= gp.quicksum([Z[i, j, b] for b in xrange(0, num_bits)]))
    return Y


def _get_3D_bin_rep(mod, X, vmax):
    l, m, n = X.shape
    Y = _get_gp_3D_arr_bin_var(mod, l, m, n)  # Y = 0 if X == 0. Y = 1 if X != 0
    for i in xrange(0, l):
        Y[i, :, :] = _get_bin_rep(mod, X[i, :, :], vmax)
    return Y


# returns numpy array of solved values
def _as_solved(X):
    m, n = X.shape
    Y = np.empty((m, n))
    for i in xrange(0, m):
        for j in xrange(0, n):
            Y[i, j] = X[i, j].X
    return Y


# # # # # # # # # # # # # # # # # # # #
#   H E L P E R   F U N C T I O N S   #
# # # # # # # # # # # # # # # # # # # #

# generate random U matrix with m rows and 2n-1 cols. vals are between 0.0 and 1.0 and rows sum to 1.0
def gen_U(m, n):
    U = np.random.rand(m, 2 * n - 1)
    rowsums = np.sum(U, 1)
    for i in xrange(m):
        U[i, :] = U[i, :] / rowsums[i]
    return U


def printnow(s):
    sys.stdout.write(s)
    sys.stdout.flush()


def np_divide_0(a, b):
    with np.errstate(divide='ignore', invalid='ignore'):
        c = np.true_divide(a, b)
        c[~ np.isfinite(c)] = 0  # -inf inf NaN
    return c
