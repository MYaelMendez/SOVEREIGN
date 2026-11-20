"""tinyCAN tests.

The constants are a MODEL fitted to three published points, not measurements of
Menlo's firmware. These tests therefore guard two different things: the physical
contention rules (which hold regardless of the constants) and the fit itself
(which is a claim about agreement with published numbers, and must not drift).
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tinycan as T


def test_topology_matches_the_published_slide():
    assert T.MOTOR_TOTAL == 25
    assert len(T.CHIPS) == 6
    assert len({c['spi'] for c in T.CHIPS}) == 3
    assert len([c for c in T.CHIPS if c['motors']]) == 5
    assert T.TICK_US == 5000.0 and T.FIRMWARE_HZ == 200


def test_spi_pairing_is_theirs():
    by_spi = {}
    for c in T.CHIPS:
        by_spi.setdefault(c['spi'], []).append(c['id'])
    assert set(by_spi['spi4']) == {'right_arm', 'left_arm'}
    assert set(by_spi['spi0']) == {'waist_neck', 'left_leg'}
    assert set(by_spi['spi1']) == {'right_leg', 'battery'}


def test_battery_polls_but_is_not_a_motor():
    bat = next(c for c in T.CHIPS if c['id'] == 'battery')
    assert bat['motors'] == 0
    r = T.poll('rows')
    assert r['replies_read'] == 25          # battery contributes no motor reply
    assert r['events'] > 25 * 4             # but it does occupy the bus


def test_one_frame_per_bus_at_a_time():
    """The physical rule: a bus carries one frame at a time. No two CAN events
    on the same bus may overlap, in either mode."""
    bus_of = {c['id']: c['bus'] for c in T.CHIPS}
    for mode in ('rows', 'burst'):
        ev, _ = T._events(mode)
        can = sorted([(a, b, bus_of[cid]) for a, b, k, cid, m in ev
                      if k in ('can_out', 'can_reply')], key=lambda e: (e[2], e[0]))
        for i in range(1, len(can)):
            pa, pb, pbus = can[i - 1]
            a, b, bus = can[i]
            if bus == pbus:
                assert a >= pb - 1e-6, f'{mode}: overlap on {bus} at {a} < {pb}'


def test_shared_spi_port_serializes():
    """Two chips on one port cannot write simultaneously."""
    spi_of = {c['id']: c['spi'] for c in T.CHIPS}
    for mode in ('rows', 'burst'):
        ev, _ = T._events(mode)
        spi = sorted([(a, b, spi_of[cid]) for a, b, k, cid, m in ev
                      if k in ('spi_write', 'spi_read')], key=lambda e: (e[2], e[0]))
        for i in range(1, len(spi)):
            pa, pb, pp = spi[i - 1]
            a, b, p = spi[i]
            if p == pp:
                assert a >= pb - 1e-6, f'{mode}: SPI overlap on {p}'


def test_no_reply_read_before_it_arrives():
    """Causality: spi_read for a motor must start after its can_reply ends."""
    for mode in ('rows', 'burst'):
        ev, _ = T._events(mode)
        reply_end = {}
        for a, b, k, cid, m in ev:
            if k == 'can_reply':
                reply_end[(cid, m)] = b
        for a, b, k, cid, m in ev:
            if k == 'spi_read':
                assert a >= reply_end[(cid, m)] - 1e-6, f'{mode}: read before arrival'


def test_burst_is_faster_and_frees_headroom():
    a, b = T.poll('rows'), T.poll('burst')
    assert b['poll_end_us'] < a['poll_end_us']
    assert b['headroom_us'] > a['headroom_us']
    assert T.compare()['speedup'] > 1.5


def test_burst_is_not_free():
    """A burst still pays a per-transfer issue cost on the RPU. Without it the
    model predicted 22/25 replies at 1.67 ms against a published 15."""
    assert T.BURST_DISPATCH_US > 0
    ev, _ = T._events('burst')
    first_writes = sorted(a for a, b, k, c, m in ev if k == 'spi_write')
    assert first_writes[1] > first_writes[0], 'burst dispatched everything at t=0'


def test_fit_to_published_throughput_points():
    """These two integers are the calibration target. If a constant changes and
    these drift, the model no longer agrees with the published slide."""
    assert T.poll('rows')['replies_by_1670us'] == 8
    assert T.poll('burst')['replies_by_1670us'] == 15


def test_aggregate_residual_is_declared_not_hidden():
    r = T.poll('rows')
    fq = r['fit_quality']
    assert '4366' in fq['rows_aggregate'] and '10.8' in fq['rows_aggregate']
    assert 'conservative' in fq['direction']
    # the model must over-estimate, never under-estimate, the published poll
    assert r['poll_end_us'] > 4366


def test_constants_are_labelled_as_a_model():
    r = T.poll('rows')
    assert 'model' in r['calibrated_to'].lower()
    assert T.doctor()['model_constants_are_assumptions'] is True


def test_sequential_nearly_exhausts_the_tick():
    """The finding the module exists to expose."""
    r = T.poll('rows')
    assert r['tick_budget_used_pct'] > 90
    assert r['fits_in_tick'] is True         # it fits, but barely


def test_determinism_same_mode_same_trace():
    assert T.trace_hash('rows') == T.trace_hash('rows')
    assert T.trace_hash('burst') == T.trace_hash('burst')
    assert T.trace_hash('rows') != T.trace_hash('burst')


def test_grade_rewards_identical_traces_only():
    a = {'trace_sha256': T.trace_hash('rows'), 'fits_in_tick': True}
    b = {'trace_sha256': T.trace_hash('rows'), 'fits_in_tick': True}
    c = {'trace_sha256': T.trace_hash('burst'), 'fits_in_tick': True}
    assert T.grade(a, b)['reward'] == 1.0
    assert T.grade(a, b)['tokens_used'] == 0
    assert T.grade(a, c)['reward'] == 0.0


def test_grade_uses_the_trace_not_the_summary():
    """Two polls with the same end time but different ordering are different
    polls. The summary would call them equal."""
    a = {'trace_sha256': 'x' * 64, 'poll_end_us': 4836.0}
    b = {'trace_sha256': 'y' * 64, 'poll_end_us': 4836.0}
    assert T.grade(a, b)['reward'] == 0.0


def test_invalid_mode_is_refused():
    with pytest.raises(ValueError):
        T.poll('sideways')


def test_every_motor_gets_exactly_one_reply():
    for mode in ('rows', 'burst'):
        _, rep = T._events(mode)
        assert len(rep) == 25
        keys = [(cid, m) for cid, t, m in rep]
        assert len(set(keys)) == 25, f'{mode}: duplicate or missing motor reply'


def test_events_are_time_ordered():
    for mode in ('rows', 'burst'):
        ev, _ = T._events(mode)
        starts = [e[0] for e in ev]
        assert starts == sorted(starts)
