from typing import Dict, List, Union, Tuple

import jsonpickle
import pickle

from consensuses.ConsensusTree import ConsensusTree
from datamodel.DAGMaf import DAGMaf
from datamodel.Poagraph import Poagraph


class TaskParameters:
    """Describes all parameters provided for single execution of pang program."""

    def __init__(self,
                 running_time: str = None,
                 multialignment_file_path: str = None,
                 multialignment_format: str = None,
                 datatype: str = None,
                 metadata_file_path: str = None,
                 blosum_file_path: str = None,
                 output_path: str = None,
                 output_po: bool = None,
                 output_fasta: bool = None,
                 output_with_nodes: bool = None,
                 verbose: bool = None,

                 raw_maf: bool = None,
                 fasta_provider: str = None,
                 email_address: str = None,
                 cache: bool = None,
                 missing_base_symbol: str = None,
                 fasta_source_file: str = None,

                 consensus_type: str = None,
                 hbmin: float = None,
                 max_cutoff_option: str = None,
                 search_range: Tuple[float, float] = None,
                 node_cutoff_option: str = None,
                 multiplier: float = None,
                 stop: float = None,
                 p: float = None
                 ):
        self.running_time: str = running_time
        self.multialignment_file_path: str = str(multialignment_file_path)
        self.multialignment_format: str = str(multialignment_format)

        self.datatype: str = str(datatype)
        self.metadata_file_path: str = str(metadata_file_path)
        self.blosum_file_path: str = str(blosum_file_path)

        self.output_path: str = str(output_path)
        self.output_po: bool = output_po
        self.generate_fasta: bool = output_fasta
        self.output_with_nodes: bool = output_with_nodes
        self.verbose: bool = verbose

        self.raw_maf: bool = raw_maf
        self.fasta_complementation_option: str = fasta_provider
        self.email: str = email_address
        self.cache: bool = cache
        self.missing_base_symbol: str = missing_base_symbol
        self.fasta_source_file: str = fasta_source_file

        self.consensus_type: str = consensus_type
        self.hbmin: float = hbmin

        self.max_cutoff_strategy: str = max_cutoff_option
        self.search_range: Tuple[float, float] = search_range

        self.node_cutoff_strategy: str = node_cutoff_option
        self.multiplier: float = multiplier

        self.stop: float = stop
        self.p: float = p


class Node:
    """Describes node of Poagraph data structure."""

    def __init__(self, node_id: int, base: str, column_id: int, block_id: int, aligned_to: int):
        self.id: int = node_id
        self.base: str = base
        self.column_id: int = column_id
        self.block_id: int = block_id
        self.aligned_to: int = aligned_to


class Sequence:
    """Describes genome sequences present in specific Poagraph."""

    def __init__(self,
                 sequence_int_id: int,
                 sequence_str_id: str,
                 metadata: Dict[str, Union[str, float]],
                 nodes_ids: List[int]):
        self.sequence_int_id: int = sequence_int_id
        self.sequence_str_id: str = sequence_str_id
        self.metadata: Dict[str, Union[str, float]] = metadata
        self.nodes_ids: List[int] = nodes_ids


class ConsensusNode:
    """Describes node present in tree of consensuses.
    It is connected with specific Poagraph structure as Poagraph nodes ids are listed here."""

    def __init__(self,
                 consensus_node_id: int,
                 name: str,
                 parent_node_id: int,
                 children_nodes_ids: List[int],
                 comp_to_all_sequences: Dict[str, float],
                 sequences_int_ids: List[int],
                 poagraph_nodes_ids: List[int],
                 mincomp: float):
        self.consensus_node_id: int = consensus_node_id
        self.name: str = name
        self.parent: int = parent_node_id
        self.children: int = children_nodes_ids
        self.comp_to_all_sequences: Dict[str, float] = comp_to_all_sequences
        self.sequences_int_ids: List[int] = sequences_int_ids
        self.nodes_ids: List[int] = poagraph_nodes_ids
        self.mincomp: float = mincomp


class MafEdge:
    """Describes edge between two maf blocks."""

    def __init__(self,
                 edge_type: Tuple[int, int] = None,
                 sequences: List[str] = None,
                 to_block: int = None):
        self.edge_type: Tuple[int, int] = edge_type
        self.sequences: List[str] = sequences
        self.to_block: int = to_block


class MafNode:
    """Describes single block in maf file converted to DAGMaf."""

    def __init__(self,
                 node_id: int = None,
                 orient: int = None,
                 out_edges: List[MafEdge] = None
                 ):
        self.node_id: int = node_id
        self.orient: int = orient
        self.out_edges: List[MafEdge] = out_edges


class PangenomeJSON:
    """Describes data generated in single pang program call and parameters."""

    def __init__(self,
                 task_parameters: TaskParameters,
                 sequences: List[Sequence],
                 nodes: List[Node],
                 dagmaf_nodes: List[MafNode],
                 consensuses_tree: List[ConsensusNode]):
        self.task_parameters: TaskParameters = task_parameters
        self.sequences: List[Sequence] = sequences
        self.nodes: List[Node] = nodes
        self.dagmaf_nodes = dagmaf_nodes
        self.consensuses_tree = consensuses_tree


def to_PangenomeJSON(task_parameters: TaskParameters = None,
                     poagraph: Poagraph = None,
                     dagmaf: DAGMaf = None,
                     consensuses_tree: ConsensusTree = None):
    """Converts pangenome specific objects to jsonable representation."""

    paths_seq_id_to_int_id = dict()
    pangenome_nodes = []
    pangenome_sequences = []
    dagmaf_nodes = []
    consensuses_nodes = []

    if poagraph:
        pangenome_nodes = [Node(node_id=node.node_id,
                                base=node.get_base(),
                                column_id=node.column_id,
                                block_id=node.block_id,
                                aligned_to=node.aligned_to)
                           for node in poagraph.nodes]

        sorted_sequences_ids = sorted(poagraph.sequences.keys())
        paths_seq_id_to_int_id = {seq_id: i for i, seq_id in enumerate(sorted_sequences_ids)}
        pangenome_sequences = [Sequence(sequence_int_id=paths_seq_id_to_int_id[seq_id],
                                        sequence_str_id=str(seq_id),
                                        metadata=poagraph.sequences[seq_id].seqmetadata,
                                        nodes_ids=[node_id for path in poagraph.sequences[seq_id].paths
                                                       for node_id in path] if task_parameters.output_with_nodes else []
                                        )
                               for seq_id in sorted_sequences_ids]

    if dagmaf:
        dagmaf_nodes = [MafNode(node_id=n.id,
                                orient=n.orient,
                                out_edges=[MafEdge(edge_type=edge.edge_type,
                                                       sequences=edge.sequences,
                                                       to_block=edge.to) for edge in n.out_edges])
                        for n in dagmaf.dagmaf_nodes]

    if consensuses_tree:
        consensuses_nodes = [ConsensusNode(consensus_node_id=consensus_node.consensus_id,
                                           name=f"CONSENSUS{consensus_node.consensus_id}",
                                           parent_node_id=consensus_node.parent_node_id,
                                           children_nodes_ids=consensus_node.children_nodes_ids,
                                           comp_to_all_sequences={seq_id: comp.value
                                                                      for seq_id, comp
                                                                      in consensus_node.compatibilities_to_all.items()},
                                           sequences_int_ids=[paths_seq_id_to_int_id[seq_id]
                                                                  for seq_id
                                                                  in consensus_node.sequences_ids
                                                                  if seq_id in paths_seq_id_to_int_id.keys()],
                                           poagraph_nodes_ids=consensus_node.consensus_path
                                               if task_parameters.output_with_nodes else [],
                                           mincomp=consensus_node.mincomp.value)
                             for consensus_node in consensuses_tree.nodes]
    return PangenomeJSON(task_parameters,
                         pangenome_sequences,
                         pangenome_nodes,
                         dagmaf_nodes,
                         consensuses_nodes
                         )


def to_json(pangenomejson: PangenomeJSON) -> str:
    return jsonpickle.encode(pangenomejson)


def to_pickle(pangenomejson: PangenomeJSON) -> str:
    return pickle.dumps(pangenomejson)


def load_pickle(s: str) -> PangenomeJSON:
    return pickle.loads(s)