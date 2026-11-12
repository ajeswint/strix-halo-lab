"""Grader boundary checks for tasks_v10.py: simple wrong or naive variants of each reference that the tests must reject.

Each entry is (what the variant gets wrong, old, new): `old` must occur exactly once in the task's ref, and the ref
with `old` replaced by `new` must FAIL run.grade on the visible seed (test_tasks_v10.TestMutants). These are typical
off-by-one, rounding, validation and tie-break mistakes, not answers. Nothing here is shown to a model.
"""

MUTANTS = {
    'v10_01_mac_address': [
        ('delimiter validation omitted', 'if delimiter not in (":", "-", ".", ""):', 'if False:'),
        ('bool accepted in addr', 'or isinstance(v, bool) or', 'or'),
    ],
    'v10_02_netstring': [
        ('leading zero allowed in length', 'len(len_bytes) > 1 and len_bytes[0] == ord(b"0")', 'False'),
        ('missing trailing comma check skipped', 'if blob[colon + 1 + n] != ord(b","):', 'if False:'),
    ],
    'v10_03_leb128': [
        ('bool accepted as int in encode', 'or isinstance(val, bool) or', 'or'),
        ('truncated sequence not detected', 'raise ValueError("truncated uleb128 sequence")', 'return val, consumed'),
    ],
    'v10_04_cron_field': [
        ('step parameter ignored and defaults to 1', 'base, step = sub[0], int(sub[1])', 'base, step = sub[0], 1'),
        ('range inversion not checked', 'if low > high:', 'if False:'),
    ],
    'v10_05_slugify_text': [
        ('invalid separator allowed', 'if not isinstance(separator, str) or len(separator) != 1 or separator not in "-_.":', 'if False:'),
        ('trailing separator not stripped after truncation', 's = s[:max_len].rstrip(separator)', 's = s[:max_len]'),
    ],
    'v10_06_isbn13': [
        ('prefix check omitted', 'if not (clean.startswith("978") or clean.startswith("979")):', 'if False:'),
        ('weights swapped in checksum', '1 if i % 2 == 0 else 3', '3 if i % 2 == 0 else 1'),
    ],
    'v10_07_http_range': [
        ('suffix <= 0 allowed', 'if not e.isdigit() or int(e) <= 0:', 'if not e.isdigit():'),
        ('end clamping to total_size - 1 omitted', 'end = min(end, total_size - 1)', 'pass'),
    ],
    'v10_08_card_deck': [
        ('Ace rank 14 formatted as string 14 instead of A', '14: "A"', '14: "14"'),
        ('suit case not lowered', 'return f"{_INV_RANKS[rank]}{suit.lower()}"', 'return f"{_INV_RANKS[rank]}{suit}"'),
    ],
    'v10_09_mobius_mertens': [
        ('mu(1) returns 0', 'if n == 1:\n        return 1', 'if n == 1:\n        return 0'),
        ('square prime factor check omitted', 'if temp % p == 0:\n                return 0', 'pass'),
    ],
    'v10_10_legendre_jacobi': [
        ('primality check omitted in legendre', 'if p % d == 0:\n            raise ValueError("p must be prime")', 'pass'),
        ('even n allowed in jacobi', 'if n < 1 or n % 2 == 0:', 'if n < 1:'),
    ],
    'v10_11_carmichael_lambda': [
        ('lambda(2^k) for k>=3 uses phi(2^k)', 'return 1 if k == 1 else (2 if k == 2 else 2**(k - 2))', 'return (p**(k - 1)) * (p - 1)'),
        ('lcm replaced by product', 'res = math.lcm(res, lam_pk(p, k))', 'res = res * lam_pk(p, k)'),
    ],
    'v10_12_continued_fraction': [
        ('terms[i] >= 1 check omitted for i > 0', 'if i > 0 and a <= 0:', 'if False:'),
        ('first continued fraction quotient incremented', 'terms.append(q)', 'terms.append(q + 1)'),
    ],
    'v10_13_mod_sqrt': [
        ('smallest root min(r, p - r) omitted', '        if t == 1:\n            return min(r, p - r)', '        if t == 1:\n            return r'),
        ('quadratic non-residue check returns 0 instead of None', 'if pow(a, (p - 1) // 2, p) != 1:\n        return None', 'if pow(a, (p - 1) // 2, p) != 1:\n        return 0'),
    ],
    'v10_14_farey_sequence': [
        ('first term (0, 1) omitted from sequence', 'seq = [(0, 1)]', 'seq = []'),
        ('count ignores baseline 1', 'return 1 + sum(phi(m) for m in range(1, n + 1))', 'return sum(phi(m) for m in range(1, n + 1))'),
    ],
    'v10_15_miller_rabin': [
        ('n=2 reported as composite', 'if n in (2, 3):\n        return True', 'if n == 3:\n        return True'),
        ('odd exponent d computed with integer division by 4', 'd //= 2', 'd //= 4'),
    ],
    'v10_16_polygon_centroid': [
        ('area returns signed area instead of unsigned', 'area = abs(cross_sum) * 0.5', 'area = cross_sum * 0.5'),
        ('centroid denominator factor 6 replaced with 2', 'cx = cx_num / (3.0 * signed_a2)', 'cx = cx_num / (1.0 * signed_a2)'),
    ],
    'v10_17_bounding_box_3d': [
        ('intersection logic uses min instead of max for lower bound', 'max(box1[0], box2[0])', 'min(box1[0], box2[0])'),
        ('union adds intersection instead of subtracting', 'vol = v1 + v2 - inter', 'vol = v1 + v2 + inter'),
    ],
    'v10_18_bipartite_match': [
        ('visited set reset omitted across DFS branches', 'dfs(u, set())', 'dfs(u, {0})'),
        ('result not sorted by left vertex', 'res.sort(key=lambda p: p[0])', 'pass'),
    ],
    'v10_19_bellman_ford_neg': [
        ('negative cycle detection omitted', 'has_neg = True\n            break', 'pass'),
        ('source distance initialized to 1 instead of 0', 'dist[source] = 0.0', 'dist[source] = 1.0'),
    ],
    'v10_20_point_winding': [
        ('boundary point returns 0 instead of None', 'return None', 'return 0'),
        ('downward edge increments instead of decrementing', 'wn -= 1', 'wn += 1'),
    ],
    'v10_21_max_clique_small': [
        ('lexicographic tie breaker omitted', 'or (len(nodes) == len(best) and nodes < best)', 'and False'),
        ('n_nodes upper bound check omitted', 'or not (1 <= n_nodes <= 20):', 'or n_nodes < 1:'),
    ],
    'v10_22_degree_sequence': [
        ('Havel-Hakimi subtracts 2 instead of 1', 'deg[i] -= 1', 'deg[i] -= 2'),
        ('realize edge sorting omitted', 'edges.sort()', 'pass'),
    ],
    'v10_23_traffic_light': [
        ('yellow light allows vehicles to pass', 'elif phase_pos < green_ns + yellow_time:\n            pass', 'elif phase_pos < green_ns + yellow_time:\n            if q_ns > 0:\n                q_ns -= 1\n                s_ns += 1'),
        ('both green times zero allowed', 'if green_ns == 0 and green_ew == 0:\n        raise ValueError("at least one green time must be positive")', 'pass'),
    ],
    'v10_24_rod_cutting_cost': [
        ('cut_cost deduction omitted from revenue', 'val = dp[i] + dp[l - i] - cut_cost', 'val = dp[i] + dp[l - i]'),
        ('length == 0 check returns None instead of empty tuple', 'return 0, ()', 'return 0, None'),
    ],
    'v10_25_token_bucket': [
        ('bucket capacity cap omitted on refill', 'tokens = min(float(capacity), tokens + (t - last_t) * refill_rate)', 'tokens = tokens + (t - last_t) * refill_rate'),
        ('timestamp non-decreasing check omitted', 'if t < last_t:\n                raise ValueError("timestamps must be non-decreasing")', 'pass'),
    ],
    'v10_26_optimal_bst': [
        ('root search weight w omitted from DP recurrence', 'cost = left + right + w', 'cost = left + right'),
        ('strict key sorting check omitted', 'if keys[i] >= keys[i + 1]:', 'if keys[i] > keys[i + 1]:'),
    ],
    'v10_27_vending_machine': [
        ('dispense fails to decrement stock', 'stock[code]["stock"] -= 1', 'pass'),
        ('coin return does not greedy sort denominations descending', 'for denom in sorted(coins.keys(), reverse=True):', 'for denom in sorted(coins.keys()):'),
    ],
    'v10_28_word_break_dp': [
        ('unmatched text returns empty list instead of None', 'if dp[n] == float("inf"):\n        return None, None', 'if dp[n] == float("inf"):\n        return 0, []'),
        ('word cost comparison allows <= instead of strictly < for new candidate', 'if new_cost < dp[nxt]', 'if new_cost <= dp[nxt]'),
    ],
    'v10_29_assembly_line_dp': [
        ('transfer penalty omitted in switch to line 1', '            nf1 = f2 + transfer2_to_1[j - 1] + line1_times[j]', '            nf1 = f2 + line1_times[j]'),
        ('exit time omitted from final total', 'tot1 = f1 + exit_times[0]', 'tot1 = f1'),
    ],
    'v10_30_connect_four': [
        ('player turns do not alternate', 'player = "R" if idx % 2 == 0 else "Y"', 'player = "R"'),
        ('column overflow check omitted', 'if r >= 6:\n            raise ValueError("column is full")', 'pass'),
    ],
    'v10_31_hex_dump': [
        ('bool accepted as start_offset', 'or isinstance(start_offset, bool) or', 'or'),
        ('non-contiguous offset check omitted', 'elif off != expected_offset:', 'elif False:'),
    ],
    'v10_32_c_string_escape': [
        ('trailing backslash error omitted', 'if i + 1 >= n:\n                raise ValueError("trailing backslash")', 'pass'),
        ('truncated hex escape allowed', 'if i + 3 >= n:\n                    raise ValueError("truncated hex escape")', 'pass'),
    ],
    'v10_33_base32_rfc': [
        ('invalid padding count accepted', 'if pad_count not in (0, 1, 3, 4, 6):', 'if False:'),
        ('unused bits check omitted', 'if any(b != "0" for b in unused):', 'if False:'),
    ],
    'v10_34_nmea_checksum': [
        ('trailing newline check omitted', 'if not line.endswith("\\r\\n"):', 'if False:'),
        ('checksum mismatch check omitted', 'if chk != int(chk_str, 16):', 'if False:'),
    ],
    'v10_35_soundex_code': [
        ('padding with zeros omitted', 'out = (first_letter + "".join(res_digits) + "000")[:4]', 'out = (first_letter + "".join(res_digits))[:4]'),
        ('first letter non-ascii check omitted', 'if not letters or any(c not in _MAP for c in letters):', 'if not letters:'),
    ],
    'v10_36_roman_numeral': [
        ('range check omitted in to_roman', 'not (1 <= val <= 3999)', 'False'),
        ('canonical equivalence check omitted in from_roman', 'or to_roman(total) != s:', ':\n        pass\n    if False:'),
    ],
    'v10_37_zigzag_varint': [
        ('zigzag negative mapping wrong', '(-2 * val - 1)', '(-2 * val)'),
        ('bool accepted as int', 'or isinstance(val, bool):', ':'),
    ],
    'v10_38_base58_btc': [
        ('leading zeros omitted in encode', 'return ("1" * leading_zeros) + "".join(reversed(chars))', 'return "".join(reversed(chars))'),
        ('invalid character check omitted in decode', 'if c not in _B58_MAP:', 'if False:'),
    ],
    'v10_39_uuid_urn': [
        ('uuid length check omitted', 'or len(uuid_bytes) != 16:', ':\n        pass\n    if False:'),
        ('hyphen positions check omitted in urn_to_uuid', 'if uuid_part[8] != "-" or uuid_part[13] != "-" or uuid_part[18] != "-" or uuid_part[23] != "-":', 'if False:'),
    ],
    'v10_40_intel_hex': [
        ('checksum verification omitted in parse', 'if sum(raw) & 0xFF != 0:\n        raise ValueError("checksum mismatch")', 'pass'),
        ('address range check omitted in format', 'or not (0 <= address <= 65535):', ':\n        pass\n    if False:'),
    ],
    'v10_41_semver_parse': [
        ('leading zero in numeric prerelease allowed', 'if p.isdigit() and len(p) > 1 and p[0] == "0":\n                raise ValueError("leading zero in numeric prerelease identifier")', 'pass'),
        ('prerelease precedence inverted against release', 'if pre1 and not pre2:\n        return -1\n    if not pre1 and pre2:\n        return 1', 'if pre1 and not pre2:\n        return 1\n    if not pre1 and pre2:\n        return -1'),
    ],
    'v10_42_tsv_record': [
        ('trailing backslash error omitted in parse', 'if i + 1 >= n:\n                    raise ValueError("trailing backslash")', 'pass'),
        ('field type check omitted in encode', 'if not isinstance(f, str):\n            raise ValueError("each field must be str")', 'pass'),
    ],
    'v10_43_syslog_timestamp': [
        ('leading space required check for single-digit day omitted', 'if day_str[0] == "0":\n        raise ValueError("days 1..9 must use space padding, not leading zero")', 'pass'),
        ('leap year max day check omitted in format', 'if not (1 <= day <= _max_day(year, month)):', 'if not (1 <= day <= 31):'),
    ],
    'v10_44_coap_option': [
        ('extended delta offset 13 omitted in encode', 'return 13, bytes([val - 13])', 'return 13, bytes([val])'),
        ('reserved nibble 15 check omitted', 'if d_nib == 15 or l_nib == 15:', 'if False:'),
    ],
    'v10_45_bcd_decode': [
        ('invalid BCD nibble check omitted', 'if high > 9 or low > 9:\n            raise ValueError("invalid BCD digit > 9")', 'pass'),
        ('nibbles swapped in encode', 'out.append((high << 4) | low)', 'out.append((low << 4) | high)'),
    ],
    'v10_46_lucas_lehmer': [
        ('s recurrence subtracts 1 instead of 2', 's = (s * s - 2) % m', 's = (s * s - 1) % m'),
        ('initial s is 3 instead of 4', 's = 4', 's = 3'),
    ],
    'v10_47_chinese_remainder': [
        ('inconsistent system check omitted', 'if diff % g != 0:\n            return None', 'pass'),
        ('extended gcd y calculation wrong', 'return g, y1, x1 - (a // b) * y1', 'return g, y1, x1 + (a // b) * y1'),
    ],
    'v10_48_pollard_rho': [
        ('prime input check omitted', 'if _is_prime(n):\n        raise ValueError("n must be composite")', 'pass'),
        ('hare advances once instead of twice', 'y = (y * y + 1) % n\n        y = (y * y + 1) % n', 'y = (y * y + 1) % n'),
    ],
    'v10_49_sum_of_divisors': [
        ('divisor_count formula uses e instead of e+1', 'res *= (e + 1)', 'res *= e'),
        ('bool accepted as int in divisor_sum', 'def divisor_sum(n):\n    if not isinstance(n, int) or isinstance(n, bool) or n < 1:', 'def divisor_sum(n):\n    if not isinstance(n, int) or n < 1:'),
    ],
    'v10_50_stern_brocot': [
        ('mediant comparison inverted in path', 'elif num * dm < den * nm:', 'elif num * dm > den * nm:'),
        ('invalid path character check omitted in fraction', 'else:\n            raise ValueError(f"invalid path character: {c}")', 'pass'),
    ],
    'v10_51_bezout_identity': [
        ('gcd(0,0) check omitted', 'if a == 0 and b == 0:\n        raise ValueError("gcd(0, 0) is undefined")', 'pass'),
        ('extended gcd y calculation wrong', 'return g, y1, x1 - (a // b) * y1', 'return g, y1, x1 + (a // b) * y1'),
    ],
    'v10_52_lucas_theorem': [
        ('prime check omitted in comb_mod_prime', 'if p < 2 or not _is_prime(p):\n        raise ValueError("p must be prime >= 2")', 'pass'),
        ('k > n check returns 1 instead of 0', 'if k > n:\n        return 0', 'if k > n:\n        return 1'),
    ],
    'v10_53_multiplicative_order': [
        ('coprimality check omitted', 'if math.gcd(a, n) != 1:\n        return None', 'pass'),
        ('divisors not sorted ascending', 'divs.sort()', 'divs.sort(reverse=True)'),
    ],
    'v10_54_totient_sum': [
        ('n=0 returns 1 instead of 0', 'if n == 0:\n        return 0', 'if n == 0:\n        return 1'),
        ('bool accepted as int', 'or isinstance(n, bool) or', 'or'),
    ],
    'v10_55_liouville_lambda': [
        ('n=1 returns -1 instead of 1', 'if n == 1:\n        return 1', 'if n == 1:\n        return -1'),
        ('lambda sign inverted', 'return 1 if omega % 2 == 0 else -1', 'return -1 if omega % 2 == 0 else 1'),
    ],
    'v10_56_factorial_mod_p': [
        ('n >= p check returns 1 instead of 0', 'if n >= p:\n        return 0', 'if n >= p:\n        return 1'),
        ('prime check omitted in factorial_mod_prime', 'if p < 2 or not _is_prime(p):\n        raise ValueError("p must be prime >= 2")', 'pass'),
    ],
    'v10_57_ramanujan_sum': [
        ('q < 1 check omitted in ramanujan_sum', 'or q < 1:', ':\n        pass\n    if False:'),
        ('mobius returns 0 for m=1', 'if m == 1:\n        return 1', 'if m == 1:\n        return 0'),
    ],
    'v10_58_continued_fraction_sqrt': [
        ('perfect square check omitted', 'if a0 * a0 == d:\n        raise ValueError("d must not be a perfect square")', 'pass'),
        ('period termination condition wrong', 'while a != 2 * a0:', 'while a != a0:'),
    ],
    'v10_59_lucas_sequence': [
        ('m < 1 check omitted', 'if n < 0 or m < 1:\n        raise ValueError("n must be >= 0 and m must be >= 1")', 'pass'),
        ('initial v0 is 0 instead of 2', 'v0, v1 = 2 % m, p_param % m', 'v0, v1 = 0, p_param % m'),
    ],
    'v10_60_engel_expansion': [
        ('non-decreasing check omitted in from_engel_expansion', 'if i > 0 and a < terms[i - 1]:\n            raise ValueError("terms must be non-decreasing")', 'pass'),
        ('ceiling division calculation wrong in to_engel_expansion', 'a = (den + num - 1) // num', 'a = den // num'),
    ],
    'v10_61_convex_hull_2d': [
        ('collinear check omitted in convex_hull_2d', 'if len(hull) < 3:\n        raise ValueError("collinear degenerate points")', 'pass'),
        ('cross product condition allows non-strict turns', 'and _cross(lower[-2], lower[-1], p) <= 0:', 'and _cross(lower[-2], lower[-1], p) < 0:'),
    ],
    'v10_62_tarjan_scc': [
        ('on_stack cross-edge update omitted', 'elif on_stack[v]:\n                low[u] = min(low[u], disc[v])', 'pass'),
        ('n_nodes < 0 check omitted', 'or n_nodes < 0:', ':\n        pass\n    if False:'),
    ],
    'v10_63_kruskal_mst': [
        ('edge tie break omitted in sorting', 'norm_edges.sort(key=lambda item: (item[0], item[1], item[2]))', 'norm_edges.sort(key=lambda item: item[0])'),
        ('edge endpoints not canonically ordered', 'norm_edges.append((w, min(u, v), max(u, v)))', 'norm_edges.append((w, u, v))'),
    ],
    'v10_64_circle_intersection': [
        ('coincident circle check omitted', 'if d < 1e-9 and abs(r1 - r2) < 1e-9:\n        return "coincident", ()', 'pass'),
        ('radius <= 0 check omitted', 'or r <= 0:', 'or False:'),
    ],
    'v10_65_lexmin_toposort': [
        ('cycle check returns empty list instead of None', 'if len(order) != n_nodes:\n        return None', 'if len(order) != n_nodes:\n        return []'),
        ('heapq pop replaced with max pop', 'u = heapq.heappop(heap)', 'u = heap.pop()'),
    ],
    'v10_66_point_in_convex': [
        ('boundary check returns inside', 'return "boundary" if on_edge else "inside"', 'return "inside"'),
        ('outside cross product check omitted', 'if cross < -1e-9:\n            return "outside"', 'pass'),
    ],
    'v10_67_dijkstra_path': [
        ('negative weight check omitted', 'or w < 0:', 'or False:'),
        ('unreachable target returns 0 instead of inf', 'if dist[target] == float("inf"):\n        return float("inf"), []', 'if dist[target] == float("inf"):\n        return 0, []'),
    ],
    'v10_68_segment_intersection': [
        ('degenerate zero-length segment check omitted', 'if p1 == p2 or p3 == p4:\n        raise ValueError("degenerate zero-length segment")', 'pass'),
        ('collinear overlap returns none', 'return "collinear_overlap", out_pts', 'return "none", None'),
    ],
    'v10_69_graph_isomorphism': [
        ('graph symmetry omitted in adjacency matrix', 'mat[u][v] = mat[v][u] = True', 'mat[u][v] = True'),
        ('n_nodes limit check omitted', 'or not (0 <= n_nodes <= 8):', 'or False:'),
    ],
    'v10_70_minimum_enclosing_circle': [
        ('empty points check omitted', 'if not isinstance(points, (list, tuple)) or len(points) == 0:\n        raise ValueError("points must be non-empty sequence")', 'pass'),
        ('single point returns 1 radius instead of 0', 'return r_list[0], 0.0', 'return r_list[0], 1.0'),
    ],
    'v10_71_articulation_points': [
        ('root child count threshold set to > 0 instead of > 1', 'if p == -1 and children > 1:\n            cuts.add(u)', 'if p == -1 and children > 0:\n            cuts.add(u)'),
        ('non-root cut condition changed from >= to >', 'if p != -1 and low[v] >= disc[u]:', 'if p != -1 and low[v] > disc[u]:'),
    ],
    'v10_72_eulerian_path_directed': [
        ('trail length check omitted', 'if len(trail) != len(edges) + 1:\n        return None', 'pass'),
        ('in-degree and out-degree swapped in degree condition', 'diff = out_deg[i] - in_deg[i]', 'diff = in_deg[i] - out_deg[i]'),
    ],
    'v10_73_tree_diameter_radius': [
        ('graph disconnected check omitted', 'if any(d == -1 for d in d0):\n        raise ValueError("graph is disconnected")', 'pass'),
        ('edges length check omitted', 'or len(edges) != n_nodes - 1:', ':\n        pass\n    if False:'),
    ],
    'v10_74_minkowski_sum_convex': [
        ('polygon vertex count check omitted', 'if not isinstance(poly, (list, tuple)) or len(poly) < 3:\n        raise ValueError("polygon must have >= 3 vertices")', 'pass'),
        ('coordinate type check omitted', 'if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, (int, float)) or not isinstance(y, (int, float)):\n            raise ValueError("coordinates must be numbers")', 'pass'),
    ],
    'v10_75_edmonds_karp_flow': [
        ('flow subtraction instead of addition', 'flow += path_flow', 'flow -= path_flow'),
        ('parallel edges overwrite rather than sum capacity', 'cap[u][v] += float(c)', 'cap[u][v] = float(c)'),
    ],
    'v10_76_elevator_scan': [
        ('reversal condition replaced with pass', 'curr_dir = "down" if curr_dir == "up" else "up"', 'pass'),
        ('clock advance on moving omitted', 'clock += 1', 'pass'),
    ],
    'v10_77_knapsack_01_exact': [
        ('weight <= 0 check omitted', 'if not isinstance(w, int) or isinstance(w, bool) or w <= 0:\n            raise ValueError("weight must be positive int")', 'pass'),
        ('tie break minimizes rather than maximizes value', 'cand[0] > ev', 'cand[0] < ev'),
    ],
    'v10_78_lcs_three_strings': [
        ('len(s) > 25 check omitted', 'if len(s) > 25:\n            raise ValueError("string length cannot exceed 25")', 'pass'),
        ('tie break prefers larger string', 'or (len(c) == len(best) and c < best)', 'or (len(c) == len(best) and c > best)'),
    ],
    'v10_79_cache_clock_second_chance': [
        ('capacity < 1 check omitted', 'if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 1:\n        raise ValueError("capacity must be int >= 1")', 'pass'),
        ('hand advance after eviction omitted', 'frames[hand] = [p, 0]\n                hand = (hand + 1) % capacity', 'frames[hand] = [p, 0]'),
    ],
    'v10_80_min_coins_change': [
        ('target < 0 check omitted', 'if not isinstance(target, int) or isinstance(target, bool) or target < 0:\n        raise ValueError("target must be non-negative int")', 'pass'),
        ('tie break minimizes rather than maximizes coin tuple', 'cand_coins > best[1]', 'cand_coins < best[1]'),
    ],
    'v10_81_turing_machine_1d': [
        ('max_steps <= 0 check omitted', 'if not isinstance(max_steps, int) or isinstance(max_steps, bool) or max_steps <= 0:\n        raise ValueError("max_steps must be positive int")', 'pass'),
        ('head movement direction inverted', 'head = head - 1 if d == "L" else head + 1', 'head = head + 1 if d == "L" else head - 1'),
    ],
    'v10_82_edit_distance_ops': [
        ('len(source) > 30 check omitted', 'if not isinstance(source, str) or isinstance(source, bool) or len(source) > 30:\n        raise ValueError("invalid source string")', 'pass'),
        ('tie-break order reversed by reversing candidates list', 'best = min(candidates, key=lambda x: x[0])', 'best = min(reversed(candidates), key=lambda x: x[0])'),
    ],
    'v10_83_round_robin_quantum': [
        ('burst <= 0 check omitted', 'if not isinstance(burst, int) or isinstance(burst, bool) or burst <= 0:\n            raise ValueError("burst must be positive int")', 'pass'),
        ('quantum <= 0 check omitted', 'if not isinstance(quantum, int) or isinstance(quantum, bool) or quantum <= 0:\n        raise ValueError("quantum must be positive int")', 'pass'),
    ],
    'v10_84_max_sum_rectangle': [
        ('ragged matrix check omitted', 'elif len(row) != c:\n            raise ValueError("ragged matrix")', 'pass'),
        ('area tie break prefers larger area', 'area < best_area', 'area > best_area'),
    ],
    'v10_85_game_of_life_torus': [
        ('cell values 0 or 1 check omitted', 'if isinstance(v, bool) or v not in (0, 1):\n                raise ValueError("cell values must be 0 or 1")', 'pass'),
        ('dead cell reproduction rule changed from 3 to 2', 'nxt[i][j] = 1 if live_nbrs == 3 else 0', 'nxt[i][j] = 1 if live_nbrs == 2 else 0'),
    ],
    'v10_86_longest_alternating_subseq': [
        ('elements must be integers check omitted', 'if not isinstance(x, int) or isinstance(x, bool):\n            raise ValueError("elements must be integers")', 'pass'),
        ('tie break prefers larger tuple instead of smaller', 'cand[1] < overall_best[1]', 'cand[1] > overall_best[1]'),
    ],
    'v10_87_particle_collision_1d': [
        ('mass <= 0 check omitted', 'if isinstance(mass, bool) or not isinstance(mass, (int, float)) or mass <= 0:\n            raise ValueError("mass must be positive number")', 'pass'),
        ('positions must be strictly increasing check omitted', 'if i > 0 and x <= pos[-1]:\n            raise ValueError("positions must be strictly increasing")', 'pass'),
    ],
    'v10_88_subset_sum_count': [
        ('elements must be positive integers check omitted', 'if not isinstance(x, int) or isinstance(x, bool) or x <= 0:\n            raise ValueError("elements must be positive integers")', 'pass'),
        ('modulo MOD omitted in subset sum count', 'new_ways = (cur_ways + prev_ways) % MOD', 'new_ways = cur_ways + prev_ways'),
    ],
    'v10_89_packet_queue_leaky': [
        ('capacity <= 0 check omitted', 'if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity <= 0:\n        raise ValueError("capacity must be positive int")', 'pass'),
        ('drop condition <= changed to strictly <', 'if buffered + float(sz) <= float(capacity) + 1e-9:', 'if buffered + float(sz) < float(capacity) - 1e-9:'),
    ],
    'v10_90_max_weight_independent_path': [
        ('weight < 0 check omitted', 'if not isinstance(w, int) or isinstance(w, bool) or w < 0:\n            raise ValueError("weights must be non-negative integers")', 'pass'),
        ('cardinality tie-break inverted', 'or (w1 == w2 and c1 < c2)', 'or (w1 == w2 and c1 > c2)'),
    ],
}
