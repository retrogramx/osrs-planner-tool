XP_TABLE = [
    0,              # Level 1 / Diff 0
    83,             # Level 2 / Diff 83
    174,            # Level 3 / Diff 91
    276,            # Level 4 / Diff 102
    388,            # Level 5 / Diff 112
    512,            # Level 6 / Diff 124
    650,            # Level 7 / Diff 138
    801,            # Level 8 / Diff 151
    969,            # Level 9 / Diff 168
    1_154,          # Level 10 / Diff 185
    1_358,          # Level 11 / Diff 204
    1_584,          # Level 12 / Diff 226
    1_833,          # Level 13 / Diff 249
    2_107,          # Level 14 / Diff 274
    2_411,          # Level 15 / Diff 304
    2_746,          # Level 16 / Diff 335
    3_115,          # Level 17 / Diff 369
    3_523,          # Level 18 / Diff 408
    3_973,          # Level 19 / Diff 450
    4_470,          # Level 20 / Diff 497
    5_018,          # Level 21 / Diff 548
    5_624,          # Level 22 / Diff 606
    6_291,          # Level 23 / Diff 667
    7_028,          # Level 24 / Diff 737
    7_842,          # Level 25 / Diff 814
    8_740,          # Level 26 / Diff 898
    9_730,          # Level 27 / Diff 990
    10_824,         # Level 28 / Diff 1_094
    12_031,         # Level 29 / Diff 1_207
    13_363,         # Level 30 / Diff 1_332
    14_833,         # Level 31 / Diff 1_470
    16_456,         # Level 32 / Diff 1_623
    18_247,         # Level 33 / Diff 1_791
    20_224,         # Level 34 / Diff 1_977
    22_406,         # Level 35 / Diff 2_182
    24_815,         # Level 36 / Diff 2_409
    27_473,         # Level 37 / Diff 2_658
    30_408,         # Level 38 / Diff 2_935
    33_648,         # Level 39 / Diff 3_240
    37_224,         # Level 40 / Diff 3_576
    41_171,         # Level 41 / Diff 3_947
    45_529,         # Level 42 / Diff 4_358
    50_339,         # Level 43 / Diff 4_810
    55_649,         # Level 44 / Diff 5_310
    61_512,         # Level 45 / Diff 5_863
    67_983,         # Level 46 / Diff 6_471
    75_127,         # Level 47 / Diff 7_144
    83_014,         # Level 48 / Diff 7_887
    91_721,         # Level 49 / Diff 8_707
    101_333,        # Level 50 / Diff 9_612
    111_945,        # Level 51 / Diff 10_612
    123_660,        # Level 52 / Diff 11_715
    136_594,        # Level 53 / Diff 12_934
    150_872,        # Level 54 / Diff 14_278
    166_636,        # Level 55 / Diff 15_764
    184_040,        # Level 56 / Diff 17_404
    203_254,        # Level 57 / Diff 19_214
    224_466,        # Level 58 / Diff 21_212
    247_886,        # Level 59 / Diff 23_420
    273_742,        # Level 60 / Diff 25_856
    302_288,        # Level 61 / Diff 28_546
    333_804,        # Level 62 / Diff 31_516
    368_599,        # Level 63 / Diff 34_795
    407_015,        # Level 64 / Diff 38_416
    449_428,        # Level 65 / Diff 42_413
    496_254,        # Level 66 / Diff 46_826
    547_953,        # Level 67 / Diff 51_699
    605_032,        # Level 68 / Diff 57_079
    668_051,        # Level 69 / Diff 63_019
    737_627,        # Level 70 / Diff 69_576
    814_445,        # Level 71 / Diff 76_818
    899_257,        # Level 72 / Diff 84_812
    992_895,        # Level 73 / Diff 93_638
    1_096_278,      # Level 74 / Diff 103_383
    1_210_421,      # Level 75 / Diff 114_143
    1_336_443,      # Level 76 / Diff 126_022
    1_475_581,      # Level 77 / Diff 139_138
    1_629_200,      # Level 78 / Diff 153_619
    1_798_808,      # Level 79 / Diff 169_608
    1_986_068,      # Level 80 / Diff 187_260
    2_192_818,      # Level 81 / Diff 206_750
    2_421_087,      # Level 82 / Diff 228_269
    2_673_114,      # Level 83 / Diff 252_027
    2_951_373,      # Level 84 / Diff 278_259
    3_258_594,      # Level 85 / Diff 307_221
    3_597_792,      # Level 86 / Diff 339_198
    3_972_294,      # Level 87 / Diff 374_502
    4_385_776,      # Level 88 / Diff 413_482
    4_842_295,      # Level 89 / Diff 456_519
    5_346_332,      # Level 90 / Diff 504_037
    5_902_831,      # Level 91 / Diff 556_499
    6_517_253,      # Level 92 / Diff 614_422
    7_195_629,      # Level 93 / Diff 678_376
    7_944_614,      # Level 94 / Diff 748_985
    8_771_558,      # Level 95 / Diff 826_944
    9_684_577,      # Level 96 / Diff 913_019
    10_692_629,     # Level 97 / Diff 1_008_052
    11_805_606,     # Level 98 / Diff 1_112_977
    13_034_431,     # Level 99 / Diff 1_228_825
]


def xp_for_level(level: int) -> int:
    """Return the minimum XP required for a given level."""
    return XP_TABLE[level - 1]


def level_for_xp(xp: int) -> int:
    """Return the level for a given XP amount."""
    for i in range(0, 99):
        if XP_TABLE[i] > xp:
            return i
    return 99


def xp_remaining(current_xp: int, target_level: int) -> int:
    """Return the XP remaining to reach a target level."""
    return xp_for_level(target_level) - current_xp
