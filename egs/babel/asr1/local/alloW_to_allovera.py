#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import argparse
import epitran
import numpy as np
import gtn
import math

def get_parser():
    parser = argparse.ArgumentParser(description="modify asr jsons to have two targets")
    parser.add_argument("--map-dir", required=True, type=str)
    parser.add_argument("--phoneme-dir", required=True, type=str)
    parser.add_argument("--phoneme-suf", required=True, type=str)
    parser.add_argument("--allphoneme-txt", required=True, type=str)
    parser.add_argument("--nlsyms-txt", required=True, type=str)
    parser.add_argument("--alloW-dir", required=True, type=str)
    parser.add_argument("--output", required=True, type=str)
    return parser


args = get_parser().parse_args()

def mat2graph(allo_mat):
    arcs = []
    for phone in range(allo_mat.shape[1]):
        n = sum(allo_mat[:, phone])
        if n > 0:
            for phoneme in range(allo_mat.shape[0]):
                if allo_mat[phoneme][phone] != 0:
                    arcs.append((phone, phoneme, 1/n))

    print("num arcs:", len(arcs))
    return arcs

def n2m(mappings, key):
    ret = []
    for p in mappings:
        if p[0] == key:
            ret.append(p[1])
    return ret


def m2n(mappings, key):
    ret = []
    for p in mappings:
        if p[1] == key:
            ret.append(p[0])
    return ret


def get_phonemes(ph_units):
    phonemes = []
    phonemes.append("<blank>")
    with open(ph_units, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for li in lines:
            m, idx = li.split()
            phonemes.append(m)
    phonemes.append("<sos>")
    return phonemes


def main(args):
    langs = ["105", "106", "107", "302", "307", "402", "000"]
    # all phonemes
    phonemes = set()
    non_phones = []
    past_nonphones = False
    with open(args.allphoneme_txt, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for li in lines:
            m, idx = li.split()
            phonemes.add(m)
            if not past_nonphones:
                non_phones.append(m)
            if m == "_":
                past_nonphones = True

    # all phones
    mappings = {}
    for lid in langs:
        pairs = []
        if lid == "105":
            name = "tur.json"
        elif lid == "106":
            name = "tgl.json"
        elif lid == "107":
            name = "vie.json"
        elif lid == "302":
            name = "kaz.json"
        elif lid == "307":
            name = "amh.json"
        elif lid == "402":
            name = "jav.json"
        elif lid == "000":
            name = "eng.json"
        with open(args.map_dir + name, "r", encoding="utf-8") as f:
            map_data = json.load(f)["mappings"]
            for p in map_data:
                pairs.append((p["phone"], p["phoneme"]))
        mappings[lid] = pairs

    phones = set()
    # non_phones = ['<unk>', '<hes>', '<noise>', '<silence>', '<v-noise>', "'", '-', '<sp>', '_']
    for lid in langs:
        with open(
            args.phoneme_dir + "/train_swbd_ph_units_" + lid + args.phoneme_suf,
            "r",
            encoding="utf-8",
        ) as f:
            lines = f.readlines()
            for li in lines:
                phoneme, idx = li.split()
                if phoneme in non_phones:
                    continue
                phone = m2n(mappings[lid], phoneme)
                if len(phone) > 0:
                    phones.update(phone)
                else:
                    print(
                        "phoneme {} not found in mapping for lang {}. adding as phone in 1-to-1 mapping.".format(
                            phoneme, lid
                        )
                    )
                    phones.add(phoneme)
                    mappings[lid].append((phoneme, phoneme))
    phones = list(phones)
    phones.sort()
    print("phones: " + str(len(phones)))
    phones = non_phones + phones
    print("non-phones + phones: " + str(len(phones)))

    phones = ["<blank>"] + phones + ["<sos>"]
    print("<blank> + nonphones + phones + <sos>: " + str(len(phones)))
    n_phones = len(phones)
    # add non-phones to mappings
    for lid in langs:
        for sym in non_phones:
            mappings[lid].append((sym, sym))
        mappings[lid].append(("<blank>", "<blank>"))
        mappings[lid].append(("<sos>", "<sos>"))

    for lid in langs:
        # load phonemes per lang
        lang_phonemes = get_phonemes(
            args.phoneme_dir + "train_swbd_ph_units_" + lid + args.phoneme_suf
        )
        n_phonemes = len(lang_phonemes)
        alloW = np.zeros((n_phonemes, n_phones))
        # errs = []
        for (n, m) in mappings[lid]:
            try:
                ni = phones.index(n)
            except ValueError:
                ni = -1
            try:
                mi = lang_phonemes.index(m)
            except ValueError:
                mi = -1
            if ni == -1 or mi == -1:
                print("ERR: ".format(n, m))
                # errs.append((n, m))
                continue
            alloW[mi][ni] = 1
        # with open("tmp", "w", encoding="utf-8") as f:
        #    for p in errs:
        #        f.write(p[0] + " " + p[1] + "\n")
        print(alloW.shape)
        print(alloW.sum(axis=-1))
        #alloW.dump(args.output + "phonemap_" + lid)

        arcs = mat2graph(alloW)

        alloW = np.exp(np.load(args.alloW_dir + lid + ".npy"))
        #print(lid)
        #print("---")
        with open(args.output+"/"+lid+"_SMbias50.txt", "w", encoding="utf-8") as out_f:
            for i,a in enumerate(arcs):
                out_f.write(phones[a[0]] + " " + lang_phonemes[a[1]] + " " + str(a[2]) + " " + str(alloW[i]) + "\n")
                #print(phones[a[0]], lang_phonemes[a[1]], a[2], alloW[i])

if __name__ == "__main__":

    main(args)