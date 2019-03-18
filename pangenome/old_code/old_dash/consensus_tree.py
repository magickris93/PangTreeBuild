import plotly.graph_objs as go

from pang.fileformats.json.JSONPangenome import JSONPangenome
import networkx as nx
from collections import deque
from app_style import colors


def toggle_node_with_children(old_tree, clicked_node):
    nodes_to_toggle = deque([clicked_node])
    while nodes_to_toggle:
        node_id = nodes_to_toggle.pop()
        old_tree.nodes[node_id]['hidden'] = not old_tree.nodes[node_id]['hidden']
        node_children = [v for u, v in old_tree.edges if u == node_id]
        nodes_to_toggle.extend(node_children)
    return old_tree


def get_tree(jsonpangenome: JSONPangenome, clck_data, old_tree):
    if not old_tree:
        tree = create_tree(jsonpangenome)
    else:
        tree = old_tree
    if clck_data:
        clicked_node = int(clck_data['points'][0]['pointIndex'])
        return toggle_node_with_children(tree, clicked_node)
    return tree


# def create_tree(jsonpangenome: JSONPangenome):
#     tree_graph = nx.DiGraph()
#     for consensus in sorted(jsonpangenome.consensuses, key=lambda c: c.id):
#         tree_graph.add_node(consensus.id,
#                             name=consensus.name,
#                             comp=consensus.comp_to_all_sequences,
#                             sequences_ids=consensus.sequences_ids,
#                             show_in_table=True,
#                             hidden=False,
#                             children_consensuses=consensus.children,
#                             mincomp=consensus.mincomp)
#         if consensus.parent is not None:
#             tree_graph.add_edge(consensus.parent, consensus.id, weight=len(consensus.sequences_ids))
#     return tree_graph


def get_node_id_to_y_pos(tree):
    node_id_to_y = {}
    leafs_ids = []
    for node_id in tree.nodes:
        if not tree.nodes[node_id]['children_consensuses']:
            leafs_ids.append(node_id)
    leafs_count = len(leafs_ids)
    min_y = 0
    max_y = 100
    leaf_distance = (max_y - min_y)/(leafs_count+1)
    for i, leaf_id in enumerate(leafs_ids):
        node_id_to_y[leaf_id] = leaf_distance * (i+1)
    nodes_to_process = deque(leafs_ids)
    while nodes_to_process:
        processed_child_id = nodes_to_process.pop()
        parents = [node_id
                   for node_id in tree.nodes
                   if processed_child_id in tree.nodes[node_id]['children_consensuses']]
        if parents:
            parent_id = parents[0]
        else:
            break
        siblings = tree.nodes[parent_id]['children_consensuses']
        all_siblings_set = all([s in node_id_to_y.keys() for s in siblings])
        if all_siblings_set:
            for s in siblings:
                if s in nodes_to_process:
                    nodes_to_process.remove(s)
        else:
            for s in siblings:
                if s not in node_id_to_y.keys() and s not in nodes_to_process:
                    nodes_to_process.appendleft(s)
            nodes_to_process.appendleft(processed_child_id)
            continue
        siblings_positions = [y for node_id, y in node_id_to_y.items() if node_id in siblings]
        left_child_pos = min(siblings_positions)
        right_child_pos = max(siblings_positions)
        node_id_to_y[parent_id] = (right_child_pos + left_child_pos) / 2
        nodes_to_process.append(parent_id)
    return node_id_to_y


# def get_consensus_tree_graph(jsonpangenome: JSONPangenome, tree, slider_value):
#     # read positions
#     node_id_to_y = get_node_id_to_y_pos(tree)
#     dots_labels_on_hover = [f'min_comp: {tree.nodes[node_id]["mincomp"]}' for node_id in range(len(node_id_to_y))]
#     dots_numbers = [f"{node_id}" for node_id in range(len(node_id_to_y))]
#     dots_positions = [[tree.nodes[node_id]["mincomp"], node_id_to_y[node_id]] for node_id in range(len(node_id_to_y))]
#     dots_x = [dot_x for [dot_x, _] in dots_positions]
#     dots_y = [dot_y for [_, dot_y] in dots_positions]
#     dots_annotations = [{'x': x_pos,
#                          'y': y_pos,
#                          'text': f"{dots_numbers[i]}",
#                          'showarrow': False}
#                         for i, (x_pos, y_pos) in enumerate(zip(dots_x, dots_y))]
#     leaves_x = []
#     leaves_y = []
#     leaves_info_text = []
#     for i in range(len(dots_x)):
#         if tree.nodes[i]['children_consensuses']:
#             continue
#         leaf_x = dots_x[i] + 0.01
#         leaf_y = dots_y[i]
#         leaf_text = get_leaf_info(i, tree, jsonpangenome)
#         leaves_x.append(leaf_x)
#         leaves_y.append(leaf_y)
#         leaves_info_text.append(leaf_text)
#     lines_x = []
#     lines_y = []
#     for u, v in tree.edges:
#         lines_x += [dots_positions[u][0], dots_positions[v][0], None]
#         lines_y += [dots_positions[u][1], dots_positions[v][1], None]
#     lines = go.Scatter(x=lines_x,
#                        y=lines_y,
#                        mode='lines',
#                        line=dict(color='rgb(210,210,210)', width=1),
#                        hoverinfo='none'
#                        )
#     line = go.Scatter(x=[slider_value, slider_value],
#                       y=[0, 100],
#                       mode='lines',
#                       line=dict(color=colors['accent']))
#     dots = go.Scatter(x=dots_x,
#                       y=dots_y,
#                       mode='markers',
#                       name='',
#                       marker=dict(symbol='circle',
#                                   size=15,
#                                   color='white',
#                                   line=dict(color='rgb(50,50,50)',
#                                             width=1),
#                                   ),
#                       text=dots_labels_on_hover,
#                       hoverinfo='text',
#                       opacity=0.8,
#                       # customdata=dots_numbers
#                       )
#     leaves_info = go.Scatter(
#         x=leaves_x,
#         y=leaves_y,
#         text=leaves_info_text,
#         mode='text+markers',
#         textposition='middle right',
#         hoverinfo='none',
#         marker=dict(symbol='line-ew-open',
#                     size=10,
#                     color='black',
#                     line=dict(color='rgb(50,50,50)', width=0.7),
#                     )
#     )
#
#     #
#     #  graph settings - layout
#     layout = dict(title='Consensuses Tree',
#                   annotations=dots_annotations,
#                   font=dict(size=12),
#                   showlegend=False,
#                   xaxis=go.layout.XAxis(dict(range=[0, 1.2], showline=False, zeroline=False, showgrid=False,
#                                              showticklabels=False,)),
#                   yaxis=go.layout.YAxis(dict(range=[0, 100], showline=False, zeroline=False, showgrid=False,
#                                              showticklabels=False,)),
#                   margin=dict(l=40, r=40, b=85, t=100),
#                   hovermode='closest',
#                   plot_bgcolor='rgb(248,248,248)',
#                   autosize=True,
#                   )
#
#     return go.Figure(
#             data=[lines, dots, leaves_info, line],
#             layout=layout
#             )

#
# def get_leaf_info(node_id, tree, jsonpangenome):
#     sequences_ids = tree.nodes[node_id]['sequences_ids']
#     sequences_names = (", ".join([jsonpangenome.sequences[seq_id].name for seq_id in sequences_ids]))
#     if len(sequences_names) < 30:
#         return sequences_names
#     else:
#         return sequences_names[:27] + '(...)'
