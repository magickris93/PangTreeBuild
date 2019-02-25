from consensus.algorithm.FindCutoff import FindMaxCutoff, FindNodeCutoff
from graph.Pangraph import Pangraph
from pathlib import Path
from copy import deepcopy
from metadata.MultialignmentMetadata import MultialignmentMetadata
from . import simple
import numpy as np
from .AlgorithmParams import AlgorithmParams
from consensus.data.SubPangraph import SubPangraph
from consensus.data.TreeConsensusManager import TreeConsensusManager
from consensus.data.ConsensusNode import ConsensusNode
from collections import deque
import logging

ap = AlgorithmParams()


def run(outputdir: Path,
        cutoffs_log_path: Path,
        pangraph: Pangraph,
        genomes_info: MultialignmentMetadata,
        max_node_strategy: FindMaxCutoff,
        node_cutoff_strategy: FindNodeCutoff,
        stop: float,
        re_consensus: bool) -> Pangraph:

    ap.hbmin = 0.6
    ap.outputdir = outputdir
    ap.cutoffs_log_path = cutoffs_log_path
    ap.genomes_info = genomes_info
    ap.max_node_strategy = max_node_strategy
    ap.node_cutoff_strategy = node_cutoff_strategy
    ap.stop = stop
    ap.re_consensus = re_consensus

    root_consensus_manager = produce_tree(pangraph)
    pangraph.set_consensus_manager(root_consensus_manager)
    return pangraph


def produce_tree(pangraph: Pangraph) -> TreeConsensusManager:
    cm = TreeConsensusManager(nodes_count=pangraph.get_nodes_count())
    root_node, root_consensus = get_root_node(pangraph)
    cm.add_node(root_node, root_consensus)
    nodes_to_process = deque([root_node])
    p = deepcopy(pangraph)
    while nodes_to_process:
        subtree_root = nodes_to_process.pop()
        children_nodes_manager = get_children_nodes(p, subtree_root)

        if ap.re_consensus:
            children_nodes_manager = reorder_consensuses(p, children_nodes_manager)

        chidren_nodes = children_nodes_manager.get_nodes()
        if len(chidren_nodes) == 1:
            continue

        for child in chidren_nodes:
            consensus = children_nodes_manager.get_consensus(child.consensus_id)
            child.parent_node_id = subtree_root.consensus_id
            child.compatibilities_to_all = pangraph.get_paths_compatibility_to_consensus(consensus)
            child_node_id = cm.add_node(child, consensus)
            subtree_root.children_nodes.append(child_node_id)
            if not node_ready(child):
                nodes_to_process.append(child)

    return cm


def node_ready(node: ConsensusNode):
    min_own_comp = min(node.get_compatibilities_to_own_sources())
    if len(node.sequences_names) in [0, 1] or min_own_comp >= ap.stop:
        return True
    return False


def get_root_node(pangraph: Pangraph):
    root_pangraph = SubPangraph(pangraph, pangraph.get_path_names())
    root_node_consensus = get_top_consensus(root_pangraph)
    root_node = ConsensusNode(sequences_names=list(pangraph.get_path_names()))
    root_node.compatibilities_to_all = pangraph.get_paths_compatibility_to_consensus(root_node_consensus)
    root_node.mincomp = min([c
                             for seq, c
                             in root_node.compatibilities_to_all.items()
                             if seq in root_node.sequences_names])
    return root_node, root_node_consensus


def get_children_nodes(orig_pangraph: Pangraph, cn: ConsensusNode) -> TreeConsensusManager:
    current_paths_names = cn.sequences_names
    op = deepcopy(orig_pangraph)
    subpangraph = SubPangraph(op, cn.sequences_names)
    local_consensus_manager = TreeConsensusManager(nodes_count=subpangraph.orig_nodes_count)
    logging.info(f"Searching children for id: {cn.consensus_id}, len: {len(cn.sequences_names)}, names: {cn.sequences_names}")
    loop_counter = 1
    while current_paths_names:
        loop_counter += 1
        subpangraph = run_poa(subpangraph, f"{cn.consensus_id}_{loop_counter}_all")
        c_to_node = subpangraph.get_paths_compatibility(0)
        max_cutoff = ap.max_node_strategy.find_max_cutoff(c_to_node, log=True)
        max_c_sources_names = get_max_compatible_sources_ids(current_paths_names, c_to_node, max_cutoff)

        subsubpangraph = SubPangraph(subpangraph.pangraph, max_c_sources_names, subpangraph.get_nodes_count())
        subsubpangraph = run_poa(subsubpangraph, f"{cn.consensus_id}_{loop_counter}_best")
        remapped_best_path = subsubpangraph.get_consensus_remapped_to_original_nodes(0)

        subpangraph.pangraph.clear_consensuses()
        subpangraph.pangraph.add_consensus(remapped_best_path)
        max_c_to_node = subpangraph.get_paths_compatibility(0)
        remapped_to_orig_best_path = subpangraph.get_consensus_remapped_to_original_nodes(0)
        node_cutoff = ap.node_cutoff_strategy.find_node_cutoff(compatibilities=max_c_to_node,
                                                               so_far_cutoffs=local_consensus_manager.get_all_leaves_mincomps(),
                                                               log = True)
        compatible_sources_names = get_max_compatible_sources_ids(current_paths_names, max_c_to_node, node_cutoff)

        node = ConsensusNode(sequences_names=list(compatible_sources_names), mincomp=node_cutoff)
        local_consensus_manager.add_node(node, remapped_to_orig_best_path)

        current_paths_names = sorted(list((set(current_paths_names) - set(compatible_sources_names))))
        subpangraph = SubPangraph(op, current_paths_names, subpangraph.orig_nodes_count)

    return local_consensus_manager


def reorder_consensuses(pangraph, tcm: TreeConsensusManager):
    current_consensus_id = None
    for seqname in tcm.get_sequences_names():
        path = pangraph.get_path(seqname)
        consensus_id_to_comp = {}
        for n in tcm.get_nodes():
            consensus = tcm.get_consensus(n.consensus_id)
            consensus_id_to_comp[n.consensus_id] = pangraph.get_path_compatibility(path, consensus)
            if seqname in n.sequences_names:
                current_consensus_id = n.consensus_id
        best_comp = max(consensus_id_to_comp.values())
        best_comp_id = [comp_id for comp_id, comp_value in consensus_id_to_comp.items()][0]
        if current_consensus_id is None:
            raise Exception(f"Unassigned consensus for {seqname}. Cannot perform reordering.")
        if best_comp != consensus_id_to_comp[current_consensus_id]:
            tcm.consensus_tree.nodes[best_comp_id].sequences_names.append(seqname)
            tcm.consensus_tree.nodes[current_consensus_id].sequences_names.remove(seqname)
    for n in tcm.get_nodes():
        if not n.sequences_names:
            tcm.remove_consensus(n.consensus_id)
    return tcm


def get_top_consensus(subpangraph: SubPangraph):
    subpangraph_with_consensus = run_poa(subpangraph, "0_consensus")
    return subpangraph_with_consensus.get_consensus_remapped_to_original_nodes(0)

#
# def find_max_cutoff(compatibility_to_node_sequences):
#     if not compatibility_to_node_sequences:
#         raise ValueError("Empty compatibilities list. Finding max cutoff is not possible.")
#
#     sorted_comp = sorted(compatibility_to_node_sequences)
#
#     if len(sorted_comp) == 1:
#         return sorted_comp[0]
#     if len(sorted_comp) == 2:
#         return sorted_comp[1]
#
#     max_diff = sorted_comp[1] - sorted_comp[0]
#     max_cutoff = sorted_comp[1]
#     for i in range(1, len(sorted_comp)-1):
#         current_diff = sorted_comp[i+1] - sorted_comp[i]
#         if current_diff >= max_diff:
#             max_diff = current_diff
#             max_cutoff = sorted_comp[i+1]
#
#     return max_cutoff
#
# def find_max_cutoff2_zastepione_przez_powyzsze(compatibility_to_node_sequences, cutoff_search_range):
#     if not compatibility_to_node_sequences:
#         raise ValueError("Empty compatibilities list. Finding max cutoff is not possible.")
#     if len(cutoff_search_range) != 2:
#         raise ValueError("Cutoff search range must have length 2.")
#     if cutoff_search_range[1] < cutoff_search_range[0]:
#         raise ValueError("For cutoff search range [x, y] x must be <= y.")
#
#     min_search_pos = round((len(compatibility_to_node_sequences)-1)*cutoff_search_range[0])
#     max_search_pos = round((len(compatibility_to_node_sequences)-1)*cutoff_search_range[1])
#     sorted_comp = sorted(compatibility_to_node_sequences)
#     if min_search_pos == max_search_pos:
#         return sorted_comp[min_search_pos]
#
#     search_range = sorted(set(sorted_comp[min_search_pos: max_search_pos+1]))
#     if len(search_range) == 1:
#         return search_range[0]
#     if len(search_range) == 2:
#         return search_range[1]
#
#     max_diff = search_range[1] - search_range[0]
#     max_cutoff = search_range[1]
#     for i in range(1, len(search_range)-1):
#         current_diff = search_range[i+1] - search_range[i]
#         if current_diff >= max_diff:
#             max_diff = current_diff
#             max_cutoff = search_range[i+1]
#
#     return max_cutoff
#
#
# def find_node_cutoff_old(compatibility_to_node_sequences, multiplier):
#     if not compatibility_to_node_sequences:
#         raise ValueError("Empty compatibilities list. Finding max cutoff.")
#     sorted_comp = sorted(set(compatibility_to_node_sequences))
#     # sorted_comp = sorted(compatibility_to_node_sequences)
#     if len(sorted_comp) == 1:
#         return sorted_comp[0]
#     elif len(sorted_comp) == 2:
#         return sorted_comp[1]
#
#     mean_distance = (sorted_comp[-1] - sorted_comp[0])/(len(sorted_comp)-1)
#     required_gap = mean_distance * multiplier
#
#     distances = np.array([sorted_comp[i + 1] - sorted_comp[i] for i in range(len(sorted_comp)-1)])
#     if any(distances >= required_gap):
#         a = np.where(distances >= required_gap)[0][0]+1
#         return sorted_comp[a]
#     else:
#         logging.warning("Cannot find node cutoff for given multiplier. Multiplier == 1 was used instead.")
#         return sorted_comp[np.where(distances >= mean_distance)[0][0]+1]
#
#
# def find_node_cutoff_old_no_multiplier(compatibility_to_node_sequences):
#     if not compatibility_to_node_sequences:
#         raise ValueError("Empty compatibilities list. Finding max cutoff.")
#     sorted_comp = sorted(compatibility_to_node_sequences)
#     if len(sorted_comp) == 1:
#         return sorted_comp[0]
#     elif len(sorted_comp) == 2:
#         return sorted_comp[1]
#
#     mean_distance = (sorted_comp[-1] - sorted_comp[0])/(len(sorted_comp)-1)
#
#     distances = np.array([sorted_comp[i + 1] - sorted_comp[i] for i in range(len(sorted_comp)-1)])
#     a = np.where(distances >= mean_distance)[0][0]+1
#     return sorted_comp[a]
#
#
# def find_node_cutoff_new(compatibility_to_node_sequences, nodeid, mincomps=None):
#     anti_granular_guard = -1
#     if not mincomps:
#         node_cutoff = find_node_cutoff_old_no_multiplier(compatibility_to_node_sequences)
#         reason = 'first child'
#     else:
#         if len(compatibility_to_node_sequences) == 1:
#             node_cutoff = compatibility_to_node_sequences[0]
#             reason = 'single comp'
#         else:
#
#             anti_granular_guard = min(mincomps)
#             sorted_comp = sorted(compatibility_to_node_sequences)
#
#             if all(anti_granular_guard <= compatibility_to_node_sequences):
#                 reason = "1 anti_granular_guard < all compatibilities"
#                 node_cutoff = sorted_comp[0]
#             elif all(anti_granular_guard > compatibility_to_node_sequences):
#                 reason = "2 anti_granular_guard > all compatibilities"
#                 node_cutoff = find_node_cutoff_old_no_multiplier(compatibility_to_node_sequences)
#             else:
#                 compatibility_to_node_sequences.append(anti_granular_guard)
#                 # sorted_comp = sorted(compatibility_to_node_sequences)
#                 mean_distance = (sorted_comp[-1] - sorted_comp[0])/(len(sorted_comp)-1)
#                 required_gap = mean_distance
#                 small_comps = [sc for sc in sorted_comp if sc <= anti_granular_guard]
#
#                 distances = np.array([small_comps[i + 1] - small_comps[i] for i in range(len(small_comps) - 1)])
#                 if any(distances >= required_gap):
#                     a = np.where(distances >= required_gap)[0][0]+1
#                     node_cutoff = small_comps[a]
#                     reason = "gap found before anti_granular_guard"
#                 else:
#                     # node_cutoff = max(small_comps)
#                     greater_than_guard = list(set(sorted_comp) - set(small_comps))
#                     # if greater_than_guard:
#                     reason = "gap not found, take first to the right"
#                     node_cutoff = min(greater_than_guard)
#                     # else:
#                     #     node_cutoff = max(small_comps) if small_comps else anti_granular_guard
#                 compatibility_to_node_sequences.pop()
#
#     # with open(get_child_file_path(ap.outputdir, "0_0_node_cutoff.csv"), "a") as output:
#     #     csv_writer = csv.writer(output, delimiter=',')
#     #     csv_writer.writerow([nodeid, str(sorted(compatibility_to_node_sequences)), anti_granular_guard, node_cutoff, reason])
#     return node_cutoff
#         # try:
#         #     left_values = [c for c in sorted_comp if c < anti_granular_guard]
#         #     left_to_guard = left_values[-1]
#         #     # right_to_guard = [c for c in sorted_comp if c > anti_granular_guard][0]
#         #     return left_to_guard
#         # except:
#         #     print("ANTI GRANULAR GUARD RETURNED!!!")
#         #     return anti_granular_guard
#         # try:
#         #     left_to_guard = [c for c in sorted_comp if c < anti_granular_guard][-1]
#         #     left_to_guard_diff = anti_granular_guard - left_to_guard
#         # except:
#         #     left_to_guard_diff = 1
#         # try:
#         #     right_to_guard = [c for c in sorted_comp if c > anti_granular_guard][0]
#         #     right_to_guard_diff = right_to_guard - anti_granular_guard
#         # except:
#         #     right_to_guard_diff = 1
#         # if right_to_guard_diff <= left_to_guard_diff:
#         #     try:
#         #         return right_to_guard
#         #     except:
#         #         pass
#         # else:
#         #     return left_to_guard
#         ###
#         #     logging.warning("Cannot find node cutoff for given multiplier. Multiplier == 1 was used instead.")
#         #     # return sorted_comp[np.where(distances >= mean_distance)[0][0]+1]
#
#
# def find_node_cutoff(compatibility_to_node_sequences, multiplier, nodeid, mincomps=None):
#     anti_granular_guard = -1
#     if not mincomps:
#         node_cutoff = find_node_cutoff_old(compatibility_to_node_sequences, multiplier)
#         reason = 'first child'
#     else:
#         # sorted_comp = sorted(set(compatibility_to_node_sequences))
#
#         if len(compatibility_to_node_sequences) == 1:
#             node_cutoff = compatibility_to_node_sequences[0]
#             reason = 'single comp'
#         else:
#             # elif len(sorted_comp) == 2:
#             #     return sorted_comp[1]
#             ################################################### do wyrzucenia
#             # if mincomps:
#             #     return min(mincomps)
#             # else:
#             #     anti_granular_guard = min(mincomps) if mincomps else []
#             #
#             #     mean_distance = (sorted_comp[-1] - sorted_comp[0]) / (len(sorted_comp) - 1)
#             #     required_gap = mean_distance * multiplier
#             #     small_comps = [sc for sc in sorted_comp if sc <= anti_granular_guard]
#             #
#             #     distances = np.array([small_comps[i + 1] - small_comps[i] for i in range(len(small_comps) - 1)])
#             #     if any(distances >= required_gap):
#             #         a = np.where(distances >= required_gap)[0][0] + 1
#             #         return small_comps[a]
#             #
#             # ###################
#             anti_granular_guard = min(mincomps)
#             # sorted_comp = sorted(set(compatibility_to_node_sequences))
#             sorted_comp = sorted(compatibility_to_node_sequences)
#
#             if all(anti_granular_guard <= compatibility_to_node_sequences):
#                 reason = "1 anti_granular_guard < all compatibilities"
#                 node_cutoff = sorted_comp[0]
#             elif all(anti_granular_guard > compatibility_to_node_sequences):
#                 reason = "2 anti_granular_guard > all compatibilities"
#                 node_cutoff = find_node_cutoff_old(compatibility_to_node_sequences, multiplier)
#             else:
#                 compatibility_to_node_sequences.append(anti_granular_guard)
#                 # sorted_comp = sorted(compatibility_to_node_sequences)
#                 mean_distance = (sorted_comp[-1] - sorted_comp[0])/(len(sorted_comp)-1)
#                 required_gap = mean_distance * multiplier
#                 small_comps = [sc for sc in sorted_comp if sc <= anti_granular_guard]
#
#                 distances = np.array([small_comps[i + 1] - small_comps[i] for i in range(len(small_comps) - 1)])
#                 if any(distances >= required_gap):
#                     a = np.where(distances >= required_gap)[0][0]+1
#                     node_cutoff = small_comps[a]
#                     reason = "gap found before anti_granular_guard"
#                 else:
#                     # node_cutoff = max(small_comps)
#                     greater_than_guard = list(set(sorted_comp) - set(small_comps))
#                     # if greater_than_guard:
#                     reason = "gap not found, take first to the right"
#                     node_cutoff = min(greater_than_guard)
#                     # else:
#                     #     node_cutoff = max(small_comps) if small_comps else anti_granular_guard
#                 compatibility_to_node_sequences.pop()
#     #
#     # with open(get_child_file_path(ap.outputdir, "0_0_node_cutoff.csv"), "a") as output:
#     #     csv_writer = csv.writer(output, delimiter=',')
#     #     csv_writer.writerow([nodeid, str(sorted(compatibility_to_node_sequences)), anti_granular_guard, node_cutoff, reason])
#     return node_cutoff
#         # try:
#         #     left_values = [c for c in sorted_comp if c < anti_granular_guard]
#         #     left_to_guard = left_values[-1]
#         #     # right_to_guard = [c for c in sorted_comp if c > anti_granular_guard][0]
#         #     return left_to_guard
#         # except:
#         #     print("ANTI GRANULAR GUARD RETURNED!!!")
#         #     return anti_granular_guard
#         # try:
#         #     left_to_guard = [c for c in sorted_comp if c < anti_granular_guard][-1]
#         #     left_to_guard_diff = anti_granular_guard - left_to_guard
#         # except:
#         #     left_to_guard_diff = 1
#         # try:
#         #     right_to_guard = [c for c in sorted_comp if c > anti_granular_guard][0]
#         #     right_to_guard_diff = right_to_guard - anti_granular_guard
#         # except:
#         #     right_to_guard_diff = 1
#         # if right_to_guard_diff <= left_to_guard_diff:
#         #     try:
#         #         return right_to_guard
#         #     except:
#         #         pass
#         # else:
#         #     return left_to_guard
#         ###
#         #     logging.warning("Cannot find node cutoff for given multiplier. Multiplier == 1 was used instead.")
#         #     # return sorted_comp[np.where(distances >= mean_distance)[0][0]+1]
#

def get_max_compatible_sources_ids(current_paths_names, compatibility_to_node_sequences, max_cutoff):
    npver = np.array(compatibility_to_node_sequences)
    path_names = np.array(current_paths_names)
    try:
        return list(path_names[np.where(npver >= max_cutoff)[0]])
    except:
        raise Exception("get_max_compatible_sources_ids ERROR")


def run_poa(subpangraph: SubPangraph, filename_prefix) -> SubPangraph:
    pangraph_with_consensus = simple.run(ap.outputdir,
                                         subpangraph.pangraph,
                                         ap.hbmin,
                                         ap.genomes_info,
                                         filename_prefix)
    subpangraph.set_pangraph(pangraph_with_consensus)
    return subpangraph
