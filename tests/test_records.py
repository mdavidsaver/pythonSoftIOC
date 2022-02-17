import multiprocessing
import numpy
import os
import pytest

from conftest import (
    create_random_prefix,
    requires_cothread,
    _clear_records,
    WAVEFORM_LENGTH,
    TIMEOUT,
    select_and_recv
)

from softioc import asyncio_dispatcher, builder, softioc

# Test file for miscellaneous tests related to records

# Test parameters
DEVICE_NAME = "RECORD-TESTS"

def test_records(tmp_path):
    # Ensure we definitely unload all records that may be hanging over from
    # previous tests, then create exactly one instance of expected records.
    from sim_records import create_records
    _clear_records()
    create_records()

    path = str(tmp_path / "records.db")
    builder.WriteRecords(path)
    expected = os.path.join(os.path.dirname(__file__), "expected_records.db")
    assert open(path).readlines()[5:] == open(expected).readlines()


def test_enum_length_restriction():
    with pytest.raises(AssertionError):
        builder.mbbIn(
            "ManyLabels",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
            "thirteen",
            "fourteen",
            "fifteen",
            "sixteen",
            "seventeen",
        )


def test_DISP_defaults_on():
    """Test that all IN record types have DISP=1 set by default"""
    in_records = [
        builder.aIn,
        builder.boolIn,
        builder.longIn,
        builder.mbbIn,
        builder.stringIn,
        builder.WaveformIn,
    ]

    record_counter = 0

    for creation_func in in_records:
        kwargs = {}
        record_counter += 1
        record_name = "DISP" + str(record_counter)

        if creation_func == builder.WaveformIn:
            kwargs = {"length": 1}

        record = creation_func(record_name, **kwargs)

        # Note: DISP attribute won't exist if field not specified
        assert record.DISP.Value() == 1


def test_DISP_can_be_overridden():
    """Test that DISP can be forced off for In records"""

    record = builder.longIn("DISP-OFF", DISP=0)
    # Note: DISP attribute won't exist if field not specified
    assert record.DISP.Value() == 0


def test_waveform_construction():
    """Test the various ways to construct a Waveform records all produce
    correct results"""

    wi = builder.WaveformIn("WI1", [1, 2, 3])
    assert wi.NELM.Value() == 3

    wi = builder.WaveformIn("WI2", initial_value=[1, 2, 3, 4])
    assert wi.NELM.Value() == 4

    wi = builder.WaveformIn("WI3", length=5)
    assert wi.NELM.Value() == 5

    wi = builder.WaveformIn("WI4", NELM=6)
    assert wi.NELM.Value() == 6

    wi = builder.WaveformIn("WI5", [1, 2, 3], length=7)
    assert wi.NELM.Value() == 7

    wi = builder.WaveformIn("WI6", initial_value=[1, 2, 3], length=8)
    assert wi.NELM.Value() == 8

    wi = builder.WaveformIn("WI7", [1, 2, 3], NELM=9)
    assert wi.NELM.Value() == 9

    wi = builder.WaveformIn("WI8", initial_value=[1, 2, 3], NELM=10)
    assert wi.NELM.Value() == 10

    # Specifying neither value nor length should produce an error
    with pytest.raises(AssertionError):
        builder.WaveformIn("WI9")

    # Specifying both value and initial_value should produce an error
    with pytest.raises(AssertionError):
        builder.WaveformIn("WI10", [1, 2, 4], initial_value=[5, 6])

    # Specifying both length and NELM should produce an error
    with pytest.raises(AssertionError):
        builder.WaveformIn("WI11", length=11, NELM=12)

def test_drvhl_hlopr_defaults():
    """Test the DRVH/L and H/LOPR default settings"""
    # DRVH/L doesn't exist on In records
    ai = builder.aIn("FOO")
    # KeyError as fields with no value are simply not present in
    # epicsdbbuilder's dictionary of fields
    with pytest.raises(KeyError):
        assert ai.LOPR.Value() is None
    with pytest.raises(KeyError):
        assert ai.HOPR.Value() is None

    ao = builder.aOut("BAR")
    with pytest.raises(KeyError):
        assert ao.LOPR.Value() is None
    with pytest.raises(KeyError):
        assert ao.HOPR.Value() is None
    with pytest.raises(KeyError):
        assert ao.DRVH.Value() is None
    with pytest.raises(KeyError):
        assert ao.DRVL.Value() is None

def test_hlopr_inherits_drvhl():
    """Test that H/LOPR values are set to the DRVH/L values"""
    lo = builder.longOut("ABC", DRVH=5, DRVL=10)

    assert lo.DRVH.Value() == 5
    assert lo.HOPR.Value() == 5
    assert lo.DRVL.Value() == 10
    assert lo.LOPR.Value() == 10

def test_hlopr_dvrhl_different_values():
    """Test you can set H/LOPR and DRVH/L to different values"""
    ao = builder.aOut("DEF", DRVL=1, LOPR=2, HOPR=3, DRVH=4)

    assert ao.DRVL.Value() == 1
    assert ao.LOPR.Value() == 2
    assert ao.HOPR.Value() == 3
    assert ao.DRVH.Value() == 4

def test_pini_always_on():
    """Test that PINI is always on for in records regardless of initial_value"""
    bi = builder.boolIn("AAA")
    assert bi.PINI.Value() == "YES"

    mbbi = builder.mbbIn("BBB", initial_value=5)
    assert mbbi.PINI.Value() == "YES"



def validate_fixture_names(params):
    """Provide nice names for the out_records fixture in TestValidate class"""
    return params[0].__name__
class TestValidate:
    """Tests related to the validate callback"""

    @pytest.fixture(
        params=[
            (builder.aOut, 7.89, 0),
            (builder.boolOut, 1, 0),
            (builder.Action, 1, 0),
            (builder.longOut, 7, 0),
            (builder.stringOut, "HI", ""),
            (builder.mbbOut, 2, 0),
            (builder.WaveformOut, [10, 11, 12], []),
            (builder.longStringOut, "A LONGER HELLO", ""),
        ],
        ids=validate_fixture_names
    )
    def out_records(self, request):
        """The list of Out records and an associated value to set """
        return request.param

    def validate_always_pass(self, record, new_val):
        """Validation method that always allows changes"""
        return True

    def validate_always_fail(self, record, new_val):
        """Validation method that always rejects changes"""
        return False

    def validate_ioc_test_func(
            self,
            device_name,
            record_func,
            child_conn,
            validate_pass: bool):
        """Start the IOC with the specified validate method"""

        builder.SetDeviceName(device_name)

        kwarg = {}
        if record_func in [builder.WaveformIn, builder.WaveformOut]:
            kwarg = {"length": WAVEFORM_LENGTH}  # Must specify when no value

        kwarg["validate"] = (
            self.validate_always_pass
            if validate_pass
            else self.validate_always_fail
        )

        record_func("VALIDATE-RECORD", **kwarg)

        dispatcher = asyncio_dispatcher.AsyncioDispatcher()
        builder.LoadDatabase()
        softioc.iocInit(dispatcher)

        child_conn.send("R")

        # Keep process alive while main thread runs CAGET
        if child_conn.poll(TIMEOUT):
            val = child_conn.recv()
            assert val == "D", "Did not receive expected Done character"

    def validate_test_runner(
            self,
            creation_func,
            new_value,
            expected_value,
            validate_pass: bool):

        parent_conn, child_conn = multiprocessing.Pipe()

        device_name = create_random_prefix()

        process = multiprocessing.Process(
            target=self.validate_ioc_test_func,
            args=(device_name, creation_func, child_conn, validate_pass),
        )

        process.start()

        from cothread.catools import caget, caput, _channel_cache

        try:
            # Wait for message that IOC has started
            select_and_recv(parent_conn, "R")


            # Suppress potential spurious warnings
            _channel_cache.purge()

            kwargs = {}
            if creation_func in [builder.longStringIn, builder.longStringOut]:
                from cothread.dbr import DBR_CHAR_STR
                kwargs.update({"datatype": DBR_CHAR_STR})

            put_ret = caput(
                device_name + ":VALIDATE-RECORD",
                new_value,
                wait=True,
                **kwargs,
            )
            assert put_ret.ok, "caput did not succeed"

            ret_val = caget(
                device_name + ":VALIDATE-RECORD",
                timeout=TIMEOUT,
                **kwargs
            )

            if creation_func in [builder.WaveformOut, builder.WaveformIn]:
                assert numpy.array_equal(ret_val, expected_value)
            else:
                assert ret_val == expected_value

        finally:
            # Suppress potential spurious warnings
            _channel_cache.purge()
            parent_conn.send("D")  # "Done"
            process.join(timeout=TIMEOUT)


    @requires_cothread
    def test_validate_allows_updates(self, out_records):
        """Test that record values are updated correctly when validate
        method allows it """

        creation_func, value, _ = out_records

        self.validate_test_runner(creation_func, value, value, True)


    @requires_cothread
    def test_validate_blocks_updates(self, out_records):
        """Test that record values are not updated when validate method
        always blocks updates"""

        creation_func, value, default = out_records

        self.validate_test_runner(creation_func, value, default, False)

class TestOnUpdate:
    """Tests related to the on_update callback, with and without
    always_update set"""

    @pytest.fixture(
        params=[
            builder.aOut,
            builder.boolOut,
            # builder.Action, This is just boolOut + always_update
            builder.longOut,
            builder.stringOut,
            builder.mbbOut,
            builder.WaveformOut,
            builder.longStringOut,
        ]
    )
    def out_records(self, request):
        """The list of Out records to test """
        return request.param

    def on_update_test_func(
        self, device_name, record_func, conn, always_update
    ):

        builder.SetDeviceName(device_name)

        li = builder.longIn("ON-UPDATE-COUNTER-RECORD", initial_value=0)

        def on_update_func(new_val):
            """Increments li record each time main out record receives caput"""
            li.set(li.get() + 1)

        kwarg = {}
        if record_func is builder.WaveformOut:
            kwarg = {"length": WAVEFORM_LENGTH}  # Must specify when no value

        record_func(
            "ON-UPDATE-RECORD",
            on_update=on_update_func,
            always_update=always_update,
            **kwarg)

        def on_update_done(_):
            conn.send("C")  # "Complete"
        # Put to the action record after we've done all other Puts, so we know
        # all the callbacks have finished processing
        builder.Action("ON-UPDATE-DONE", on_update=on_update_done)

        dispatcher = asyncio_dispatcher.AsyncioDispatcher()
        builder.LoadDatabase()
        softioc.iocInit(dispatcher)

        conn.send("R")  # "Ready"

        print("CHILD: Sent R over Connection to Parent")

        # Keep process alive while main thread runs CAGET
        if conn.poll(TIMEOUT):
            val = conn.recv()
            assert val == "D", "Did not receive expected Done character"

        print("CHILD: Received exit command, child exiting")

    def on_update_runner(self, creation_func, always_update, put_same_value):
        parent_conn, child_conn = multiprocessing.Pipe()

        device_name = create_random_prefix()

        process = multiprocessing.Process(
            target=self.on_update_test_func,
            args=(device_name, creation_func, child_conn, always_update),
        )

        process.start()

        print("PARENT: Child started, waiting for R command")

        from cothread.catools import caget, caput, _channel_cache

        try:
            # Wait for message that IOC has started
            select_and_recv(parent_conn, "R")

            print("PARENT: received R command")


            # Suppress potential spurious warnings
            _channel_cache.purge()

            # Use this number to put to records - don't start at 0 as many
            # record types default to 0 and we usually want to put a different
            # value to force processing to occur
            count = 1

            print("PARENT: begining While loop")

            while count < 4:
                put_ret = caput(
                    device_name + ":ON-UPDATE-RECORD",
                    9 if put_same_value else count,
                    wait=True,
                )
                assert put_ret.ok, f"caput did not succeed: {put_ret.errorcode}"

                print(f"PARENT: completed caput with count {count}")

                count += 1

            print("PARENT: Put'ing to DONE record")

            caput(
                device_name + ":ON-UPDATE-DONE",
                1,
                wait=True,
            )

            print("PARENT: Waiting for C command")

            # Wait for action record to process, so we know all the callbacks
            # have finished processing (This assumes record callbacks are not
            # re-ordered, and will run in the same order as the caputs we sent)
            select_and_recv(parent_conn, "C")

            print("PARENT: Received C command")

            ret_val = caget(
                device_name + ":ON-UPDATE-COUNTER-RECORD",
                timeout=TIMEOUT,
            )
            assert ret_val.ok, \
                f"caget did not succeed: {ret_val.errorcode}, {ret_val}"

            print(f"PARENT: Received val from COUNTER: {ret_val}")


            # Expected value is either 3 (incremented once per caput)
            # or 1 (incremented on first caput and not subsequent ones)
            expected_val = 3
            if put_same_value and not always_update:
                expected_val = 1

            assert ret_val == expected_val

        finally:
            # Suppress potential spurious warnings
            _channel_cache.purge()

            print("PARENT:Sending Done command to child")
            parent_conn.send("D")  # "Done"
            process.join(timeout=TIMEOUT)
            print(f"PARENT: Join completed with exitcode {process.exitcode}")
            if process.exitcode is None:
                pytest.fail("Process did not terminate")

    @requires_cothread
    def test_on_update_false_false(self, out_records):
        """Test that on_update works correctly for all out records when
        always_update is False and the put'ed value is always different"""
        self.on_update_runner(out_records, False, False)

    @requires_cothread
    def test_on_update_false_true(self, out_records):
        """Test that on_update works correctly for all out records when
        always_update is False and the put'ed value is always the same"""
        self.on_update_runner(out_records, False, True)

    @requires_cothread
    def test_on_update_true_true(self, out_records):
        """Test that on_update works correctly for all out records when
        always_update is True and the put'ed value is always the same"""
        self.on_update_runner(out_records, True, True)

    @requires_cothread
    def test_on_update_true_false(self, out_records):
        """Test that on_update works correctly for all out records when
        always_update is True and the put'ed value is always different"""
        self.on_update_runner(out_records, True, False)
