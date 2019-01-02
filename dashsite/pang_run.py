from io import StringIO

from pang.Pangenome import Pangenome
from pang.userio import pathtools
from pang.fileformats.json import writer as jsonwriter
from pathlib import Path
from os import getcwd

from base64 import b64decode

def run_pang(multialignment_contents,
             metadata_contents,
             fasta_option,
             consensus_option,
             hbmin,
             r,
             multiplier,
             stop,
             re_consensus,
             anti_fragmentation_value):
    #maf
    content_type, content_string = multialignment_contents.split(',')
    maf_str = b64decode(content_string).decode('ascii')

    #metadata
    content_type, content_string = metadata_contents.split(',')
    metadata_str = b64decode(content_string).decode('ascii')

    output_dir = pathtools.create_default_output_dir(Path(getcwd()))

    pangenome = Pangenome(multialignment=StringIO(maf_str),
                  metadata=metadata_str)
    # if fasta_option:
    #     pass
    #     # get fasta zip?
    #     # pangenome.generate_fasta_files(pathtools.create_child_dir(args.output, 'fasta'))
    if consensus_option:
        pangenome.generate_consensus(pathtools.create_child_dir(output_dir, 'consensus'),
                             consensus_option,
                             hbmin,
                             r,
                             multiplier,
                             stop,
                             re_consensus,
                             anti_fragmentation_value
                             )

    json_path = jsonwriter.save(output_dir, pangenome)
    return pangenome, json_path


def decode_json(pangenome_json_contents):
    content_type, content_string = pangenome_json_contents.split(',')
    json_str = b64decode(content_string).decode('ascii')
    return json_str
