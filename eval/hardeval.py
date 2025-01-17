#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals
import os, argparse
from collections import defaultdict, Counter
from .utils_hardeval import enforce_valid_bio2_labeling, convert_bio2_to_bilou, compute_TER, get_word_label_count_dict, get_diff_indices, write_table

doc="""Given NER predictions and training data, compute token error rate
on various subsets of tokens. 

WARNING: labels must be in BIO-2 format.
"""

from typing import NamedTuple
  
# creating a class
class Arguments(NamedTuple):
    write_dir: str
    pred: str
    train: str
    strict: bool




def main(write_dir: str, pred: str, train: str, strict: bool = False):
    """
    parser = argparse.ArgumentParser(description=doc)
    msg = ("Use strict mode for evaluation of tokens with surprising labels "
           "(evaluate tokens whose labels was never observed in training only)")
    parser.add_argument("-s", "--strict", action="store_true", help=msg)
    msg = ("(optional) path of directory in which we write a vocab file and "
           "evaluation file for each subset of tokens")
    parser.add_argument("-w", "--write-dir", required=False, help=msg)
    msg = ("Path of training data (text file containing whitespace-separate "
           "columns, with tokens in the first column, and gold BIO-2 labels in the last "
           "column).")
    parser.add_argument("train", help=msg)
    msg = ("Path of predictions (text file containing whitespace-separate "
           "columns, with tokens in the first column, and gold and predicted "
           "BIO-2 labels in the last 2 columns).")
    parser.add_argument("pred", help=msg)
    # args = parser.parse_args()
    """
    args = Arguments(write_dir, pred, train, strict)


    if args.write_dir:
        if os.path.exists(args.write_dir):
            msg = "Error: {} already exists".format(args.write_dir)
            raise ValueError(msg)
        os.mkdir(args.write_dir)

    print("\nReading predictions from {}...".format(os.path.abspath(args.pred)))
    word_col_ix = 0
    gold_col_ix = -2
    pred_col_ix = -1
    test_tokens = []
    test_gold_bio = []
    test_pred_bio = []
    with open(args.pred) as f:
        for line in f:
            elems = line.strip().split()
            if len(elems):
                test_tokens.append(elems[word_col_ix])
                test_gold_bio.append(elems[gold_col_ix])
                test_pred_bio.append(elems[pred_col_ix])
    if not len(test_tokens):
        msg = "Error: 0 tokens read"
        raise ValueError(msg)
    print("Nb tokens in test set: {}".format(len(test_tokens)))

    print("\nReading training data from {}...".format(os.path.abspath(args.train)))
    train_tokens = []
    train_gold_bio = []
    word_col_ix = 0
    gold_col_ix = -1
    with open(args.train) as f:
        for line in f:
            elems = line.strip().split()
            if len(elems):
                train_tokens.append(elems[word_col_ix])
                train_gold_bio.append(elems[gold_col_ix])

    if len(train_tokens) == 0:
        msg = "Error: 0 tokens read"
        raise ValueError(msg)
    print("Nb tokens in training set: {}".format(len(train_tokens)))

    # Store vocabs
    train_vocab = set(train_tokens)
    test_vocab = set(test_tokens)

    # Enforce valid BIO-2 labeling
    try:
        enforce_valid_bio2_labeling(train_gold_bio)
    except Exception as ex:
        print(ex)
        print('Warning: Exception in verifying IOB-2 tags on training data')

    try:
        enforce_valid_bio2_labeling(test_gold_bio)    
    except Exception as ex:
        print(ex)
        print('Warning: Exception in verifying IOB-2 tags on test data')

    #enforce_valid_bio2_labeling(test_pred_bio)

    # Convert label encoding from BIO-2 to BILOU
    train_gold_bilou = convert_bio2_to_bilou(train_gold_bio)
    test_gold_bilou = convert_bio2_to_bilou(test_gold_bio)
    test_pred_bilou = convert_bio2_to_bilou(test_pred_bio)

    # Map words to their labels in the training and test sets
    train_word_to_labels = defaultdict(list)
    for word, label in zip(train_tokens, train_gold_bilou):
        train_word_to_labels[word].append(label)
    test_word_to_labels = defaultdict(list)
    for word, label in zip(test_tokens, test_gold_bilou):
        test_word_to_labels[word].append(label)

    # Extract IO prefix and entity type from BILOU labels
    train_gold_io = ["O" if lab == "O" else "I" for lab in train_gold_bilou]
    test_gold_io = ["O" if lab == "O" else "I" for lab in test_gold_bilou]
    test_pred_io = ["O" if lab == "O" else "I" for lab in test_pred_bilou]

    ####################################################################
    # Compute subsets of test tokens, then compute evaluation metrics on
    # those tokens
    ####################################################################
    to_eval = []

    # All test tokens
    keep_all = range(len(test_tokens))
    eval_name = "all"
    to_eval.append((keep_all, eval_name))

    #keep_all_in_mention = [i for i in keep_all if test_gold_io[i] == "I" or test_pred_io[i] == "I"]
    #eval_name = "all-in-mention"
    #to_eval.append((keep_all_in_mention, eval_name))
    
    # Unseen words
    unseen = test_vocab.difference(train_vocab)
    keep_unseen = [i for i in keep_all if test_tokens[i] in unseen]
    keep_unseen_I = []
    keep_unseen_O = []
    for i in keep_unseen:
        if test_gold_io[i] == "I":
            keep_unseen_I.append(i)
        else:
            keep_unseen_O.append(i)
    eval_name = "unseen-I"
    to_eval.append((keep_unseen_I, eval_name))
    eval_name = "unseen-O"
    to_eval.append((keep_unseen_O, eval_name))
    eval_name = "unseen-all"
    to_eval.append((keep_unseen, eval_name))

    # O tokens that were usually or exclusively I in training, and vice-versa
    word_io_count = get_word_label_count_dict(train_tokens, train_gold_io)
    test_indices_I = []
    test_indices_O = []
    for i,label in enumerate(test_gold_io):
        if label == "I":
            test_indices_I.append(i)
        else:
            test_indices_O.append(i)
    test_tokens_I = [test_tokens[i] for i in test_indices_I]
    test_labels_I = ["I" for _ in test_indices_I]
    indices = get_diff_indices(word_io_count, test_tokens_I, test_labels_I, strict=args.strict)
    keep_diff_I = [test_indices_I[i] for i in indices]
    test_tokens_O = [test_tokens[i] for i in test_indices_O]
    test_labels_O = ["O" for _ in test_indices_O]
    indices = get_diff_indices(word_io_count, test_tokens_O, test_labels_O, strict=args.strict)
    keep_diff_O = [test_indices_O[i] for i in indices]
    eval_name = "diff-I"
    to_eval.append((keep_diff_I, eval_name))
    eval_name = "diff-O"
    to_eval.append((keep_diff_O, eval_name))

    # Write IO prefix frequencies in training set for seen test words
    # (excluding "O")
    if args.write_dir:
        keys = ["I", "O"]
        io_info = []
        for word in test_vocab.intersection(train_vocab):
            io_fd = {}
            if word in word_io_count:
                io_fd = word_io_count[word]
            io_info.append([word] + [str(io_fd[k]) if k in io_fd else "0" for k in keys])
        io_info = sorted(io_info, key=lambda x:x[0])
        path = "{}/class_freqs_for_seen_words_IO.tsv".format(args.write_dir)
        header = ["Word"] + keys
        write_table(io_info, path, header=header, delim="\t")

    # I-X tokens that were usually I, but whose entity type was usually
    # (or exclusively) not X.
    train_indices_I = []
    for i,label in enumerate(train_gold_io):
        if label == "I":
            train_indices_I.append(i)
    train_tokens_I = [train_tokens[i] for i in train_indices_I]
    train_etypes_I = [train_gold_bilou[i][2:] for i in train_indices_I]
    word_etype_count = get_word_label_count_dict(train_tokens_I, train_etypes_I)
    usually_I = set()
    for word, io_fd in word_io_count.items():
        i_count = 0
        o_count = 0
        if "I" in io_fd:
            i_count = io_fd["I"]
        if "O" in io_fd:
            o_count = io_fd["O"]
        if i_count >= o_count:
            usually_I.add(word)
    test_indices_UI = [i for i in test_indices_I if test_tokens[i] in usually_I]
    test_tokens_UI = [test_tokens[i] for i in test_indices_UI]
    test_etypes_UI = [test_gold_bilou[i][2:] for i in test_indices_UI]
    indices = get_diff_indices(word_etype_count, test_tokens_UI, test_etypes_UI, strict=args.strict)
    keep_diff_etype = [test_indices_UI[i] for i in indices]
    eval_name = "diff-etype"
    to_eval.append((keep_diff_etype, eval_name))
    
    # Write entity type frequencies in training set for seen test words
    # (excluding "O")
    if args.write_dir:
        keys = list(set(train_etypes_I))
        etype_info = []
        for word in test_vocab.intersection(word_etype_count.keys()):
            etype_fd = word_etype_count[word]
            etype_info.append([word] + [str(etype_fd[k]) if k in etype_fd else "0" for k in keys])
        etype_info = sorted(etype_info, key=lambda x:x[0])
        path = "{}/class_freqs_for_seen_words_etype.tsv".format(args.write_dir)
        header = ["Word"] + keys
        write_table(etype_info, path, header=header, delim="\t")

    # Combine the unseen and diff indices
    keep_diff_all = sorted(set(keep_diff_I + keep_diff_O + keep_diff_etype))
    eval_name = "diff-all"
    to_eval.append((keep_diff_all, eval_name))

    # Combine the unseen and diff indices
    keep_hard_all = sorted(set(keep_diff_all + keep_unseen_I + keep_unseen_O))
    eval_name = "all-unseen+diff"
    to_eval.append((keep_hard_all, eval_name))

    # Evaluate        
    res_nb_tokens = {}
    res_nb_words = {}
    res_nb_errors = {}
    res_ter = {}
    for keep, eval_name in to_eval:
        t = [test_tokens[i] for i in keep]
        p = [test_pred_bilou[i] for i in keep]
        g = [test_gold_bilou[i] for i in keep]
        ter, nb_errs = compute_TER(p, g)
        res_nb_tokens[eval_name] = len(t)
        res_nb_words[eval_name] = len(set(t))
        res_nb_errors[eval_name] = nb_errs
        res_ter[eval_name] = ter
        if args.write_dir:
            # Write tokens with their predicted and gold labels
            header = "Index Token Gold Predicted Correct?".split()
            info = []
            for ix, token, gold, pred in zip(keep, t, g, p):
                correct = "WRONG"
                if gold == pred:
                    correct = "CORRECT"
                info.append([str(ix), token, gold, pred, correct])
            path = "{}/eval-{}.tsv".format(args.write_dir, eval_name)
            write_table(info, path, header=header, delim="\t")
            # Write vocab
            word_to_freq = Counter(t)
            vocab = sorted(word_to_freq.items(), key=lambda x:x[1], reverse=True)
            vocab = [[w,str(c)] for w,c in vocab]
            header = ["Word", "NbEvaluated"]
            path = "{}/vocab-{}.tsv".format(args.write_dir, eval_name)
            write_table(vocab, path, header=header, delim="\t")

    # Write results
    res_header = ["Test tokens", "Nb tokens", "Nb words", "Nb errors", "Token error rate"]
    res_table = []
    ename_to_row_ix = {}
    for i, (keep, e) in enumerate(to_eval):
        row = [e, str(res_nb_tokens[e]), str(res_nb_words[e]), str(res_nb_errors[e]), "{:.4f}".format(res_ter[e])]
        res_table.append(row)
        ename_to_row_ix[e] = i
    if args.write_dir:
        path = "{}/results.tsv".format(args.write_dir)
        write_table(res_table, path, header=res_header, delim="\t")

    # Pretty print results
    strict_on_or_off = "OFF"
    if args.strict:
        strict_on_or_off = "ON"
    print("\nStrict mode: {}\n".format(strict_on_or_off))
    col_widths = [len(s) for s in res_header]
    for row in res_table:
        for i,x in enumerate(row):
            width = len(x)
            if width > col_widths[i]:
                col_widths[i] = width

    delim = "   "
    print_row = lambda row:print(delim.join("{msg: >{fill}}".format(msg=x, fill=w) for x,w in zip(row, col_widths)))
    line = "-" * (sum(col_widths) + len(delim)*(len(col_widths)-1))

    print(line)
    print_row(res_header)
    print(line)
    print_row(res_table[ename_to_row_ix["all"]])
    print(line)

    eval_names = ["unseen-I", "unseen-O", "unseen-all"]
    for eval_name in eval_names:
        print_row(res_table[ename_to_row_ix[eval_name]])
    print(line)

    eval_names = ["diff-I", "diff-O", "diff-etype", "diff-all"]
    for eval_name in eval_names:
        print_row(res_table[ename_to_row_ix[eval_name]])
    print(line)

    print_row(res_table[ename_to_row_ix["all-unseen+diff"]])
    print(line)

    # Print average score on unseen and diff
    score = (res_ter["unseen-all"] + res_ter["diff-all"]) / 2
    print("\n\nAvg TER on unseen and diff: {:.4f}\n\n".format(score))


if __name__ == "__main__":
    main()
