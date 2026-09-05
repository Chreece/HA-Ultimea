"""Execute production runtime/entities with an in-memory BLE peer (no HA/BT I/O)."""
from __future__ import annotations

import asyncio
import importlib.util
import json
from enum import IntFlag, StrEnum
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / 'custom_components' / 'ultimea'
CAPTURE = json.loads((ROOT / 'tests/fixtures/d80_style_capture.json').read_text())


@pytest.fixture
def code(monkeypatch):
    """Stub only external HA/Bleak APIs; load the real integration modules."""
    def module(name, **attrs):
        mod = ModuleType(name)
        mod.__path__ = []
        mod.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, mod)
        return mod

    class Entity:
        async def async_added_to_hass(self):
            pass

    class MediaFlags(IntFlag):
        TURN_ON=1; TURN_OFF=2; VOLUME_SET=4; VOLUME_STEP=8
        VOLUME_MUTE=16; SELECT_SOURCE=32; SELECT_SOUND_MODE=64

    class MediaState(StrEnum):
        ON='on'; OFF='off'

    module('homeassistant')
    module('homeassistant.components')
    bt = module('homeassistant.components.bluetooth',
        BluetoothReachabilityIntent=SimpleNamespace(CONNECTION='connection'),
        async_last_service_info=lambda *a, **k: SimpleNamespace(rssi=-50, name='D80'),
        async_ble_device_from_address=lambda *a, **k: object())
    module('homeassistant.config_entries', ConfigEntry=object)
    module('homeassistant.core', HomeAssistant=object, callback=lambda fn: fn)
    module('homeassistant.const', EntityCategory=SimpleNamespace(DIAGNOSTIC='diagnostic'))
    module('homeassistant.exceptions', HomeAssistantError=type('HomeAssistantError', (Exception,), {}))
    module('homeassistant.helpers')
    module('homeassistant.helpers.entity', Entity=Entity)
    module('homeassistant.helpers.entity_platform', AddConfigEntryEntitiesCallback=object)
    module('homeassistant.helpers.device_registry', CONNECTION_BLUETOOTH='bluetooth', DeviceInfo=dict)
    module('homeassistant.components.sensor', SensorEntity=type('SensorEntity', (Entity,), {}))
    module('homeassistant.components.button', ButtonEntity=type('ButtonEntity', (Entity,), {}))
    module('homeassistant.components.number', NumberEntity=type('NumberEntity', (Entity,), {}),
           NumberMode=SimpleNamespace(SLIDER='slider'))
    module('homeassistant.components.media_player',
        MediaPlayerEntity=type('MediaPlayerEntity', (Entity,), {}),
        MediaPlayerEntityFeature=MediaFlags, MediaPlayerState=MediaState,
        MediaPlayerDeviceClass=SimpleNamespace(SPEAKER='speaker'))
    module('bleak', BleakClient=object)
    module('bleak.backends')
    module('bleak.backends.device', BLEDevice=object)
    module('bleak_retry_connector', establish_connection=AsyncMock())
    package = module('_ultimea_style_test', UltimeaRuntimeData=SimpleNamespace)
    package.__path__ = [str(COMPONENT)]
    loaded = SimpleNamespace(bluetooth=bt)
    for name in ('const', 'protocol', 'eq_style', 'profiles', 'models', 'device', 'runtime',
                 'entity', 'sensor', 'button', 'media_player', 'number'):
        fullname = f'_ultimea_style_test.{name}'
        spec = importlib.util.spec_from_file_location(fullname, COMPONENT / f'{name}.py')
        mod = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, fullname, mod)
        spec.loader.exec_module(mod)
        setattr(loaded, name, mod)
    return loaded


class Peer:
    def __init__(self, code, device, mode=8):
        self.code, self.device, self.mode = code, device, mode
        self.is_connected = True
        self.trace = []
        self.short_ack = False
        self.wrong_profile_first = False
        self.mode_reply = None
        self.bad_safe = False
        self.curves = {
            7: code.protocol.build_equalizer_payload((0,) * 10),
            8: code.eq_style.build_style_payload('rock'),
        }
        c=code.const
        self.services=[SimpleNamespace(characteristics=[SimpleNamespace(uuid=u) for u in c.TRANSPORT_UUIDS[c.TRANSPORT_COMMON]])]
        self.start_notify=AsyncMock()
        self.stop_notify=AsyncMock()

    async def disconnect(self):
        self.is_connected=False
        self.device._disconnected(self)

    def rx(self, group, command, data):
        raw=bytearray(self.code.protocol.build_command(group,command,data));raw[0]=0xbb
        self.device._notification(None, raw)

    async def write_gatt_char(self, uuid, packet, response=False):
        group,command=packet[3:5]; data=bytes(packet[5:-1])
        self.trace.append((group,command,data))
        await asyncio.sleep(0)  # exercise interleaved concurrent requests
        if group==0 and command==1:
            reply = b'\x00\x00' if self.bad_safe else self.code.protocol.build_safe_code_pair(data[0]^255)
        elif group==0 and command==0:
            reply=bytes.fromhex('000101010101010101010100010100010101')
        elif group==1:
            reply={1:b'\x01\x00',2:b'Poseidon D80 Boom',4:b'TEST-SERIAL',5:b'\x0a\x00',
                   6:b'\x00',7:b'\x08',8:bytes([self.mode]),10:b'\x00',12:b'\x01',
                   13:b'\x01',14:b'\x01',15:b'\x03',23:b'\x0f\x00',24:b'\x01'}.get(command,b'')
            if command==8 and self.mode_reply is not None:
                reply=self.mode_reply
        elif group==2 and command==4:
            self.mode=data[0]
            if len(data)==1:
                reply=self.curves[data[0]]
                if self.short_ack:
                    self.rx(group,command,data)
                if self.wrong_profile_first:
                    self.rx(group,command,self.curves[7 if data[0]==8 else 8])
            else:
                self.curves[data[0]]=data
                reply=data
        else:
            reply=data
        self.rx(group,command,reply)


def device_with_peer(code, mode=8):
    dev=code.runtime.UltimeaDevice(SimpleNamespace(), '00:00:00:00:00:01','Test D80')
    c=code.const
    dev.identity.model=c.VERIFIED_MODEL
    dev.restore_capabilities()
    dev._available=True
    dev.state.power=True
    dev._transport=c.TRANSPORT_COMMON
    dev._transport_candidates=[c.TRANSPORT_COMMON]
    dev._write_uuid=c.WRITE_UUID
    dev._notify_uuid=c.NOTIFY_UUID
    peer=Peer(code,dev,mode)
    dev._client=peer
    return dev,peer


@pytest.mark.parametrize('preset,label',[
    ('bass','STYLE_BASS_CORNER'),('rock','STYLE_ROCK_CORNER'),
    ('pop','STYLE_POP_CORNER'),('classical','STYLE_CLASSICAL_CORNER'),
    ('flat','STYLE_RESET_CENTER_2')])
def test_every_style_curve_matches_captured_write_and_echo(code,preset,label):
    events=[e for e in CAPTURE['events'] if e['label']==label]
    assert [e['direction'] for e in events]==['TX','RX']
    payload=code.eq_style.build_style_payload(preset)
    for e in events:
        assert payload==bytes.fromhex(e['data_hex'])
        frame=bytearray(code.protocol.build_command(2,4,payload))
        if e['direction']=='RX': frame[0]=0xbb
        assert bytes(frame)==bytes.fromhex(e['frame_hex'])
    assert code.eq_style.identify_style_preset(code.eq_style.parse_d80_profile(payload).gains_tenths_db)==preset


def test_style_activation_capture_is_one_byte_query_then_full_curve(code):
    events=[e for e in CAPTURE['events'] if e['label']=='CUSTOM_STYLE_TAB']
    assert events[0]['data_hex']=='08'
    assert len(bytes.fromhex(events[1]['data_hex']))==41
    assert code.eq_style.parse_d80_profile(bytes.fromhex(events[1]['data_hex'])).profile==8


def test_unknown_preset_and_nonexact_curve_never_become_flat(code):
    with pytest.raises(ValueError): code.eq_style.build_style_payload('invented')
    assert code.eq_style.identify_style_preset((1,)+(0,)*9) is None


@pytest.mark.parametrize('kind',['length','profile','frequency','gain'])
def test_bad_curves_are_rejected(code,kind):
    p=bytearray(code.eq_style.build_style_payload('rock'))
    if kind=='length': p.pop()
    elif kind=='profile': p[0]=0x55
    elif kind=='frequency': p[1]=0
    else: p[3:5]=(61).to_bytes(2,'little',signed=True)
    assert code.eq_style.parse_d80_profile(bytes(p)) is None
    dev,_=device_with_peer(code)
    f=code.protocol.UltimeaFrame(0xbb,2,4,bytes(p),b'')
    assert not dev._handle_control_frame(f)
    assert dev.state.eq_band_gains_tenths_db is None


def test_style_selection_waits_for_matching_complete_curve(code):
    async def run():
        dev,peer=device_with_peer(code)
        peer.short_ack=True;peer.wrong_profile_first=True
        await dev.async_set_sound_mode(code.const.SoundMode.STYLE)
        assert dev.state.sound_mode is code.const.SoundMode.STYLE
        assert dev.state.eq_profile_id==8
        assert dev.state.eq_band_gains_tenths_db==code.eq_style.STYLE_PRESETS['rock']
        assert peer.trace[:2][0]==(1,1,b'')
        assert peer.trace[1][:2]==(0,1)
        assert peer.trace[-1]==(2,4,b'\x08')
    asyncio.run(run())


@pytest.mark.parametrize('preset',['bass','rock','pop','classical','flat'])
def test_buttons_send_proven_curves_and_publish_only_echoed_values(code,preset):
    async def run():
        dev,peer=device_with_peer(code,mode=1)
        button=code.button.UltimeaStyleButton(dev,preset)
        await button.async_press()
        assert peer.trace[-1]==(2,4,code.eq_style.build_style_payload(preset))
        assert dev.state.sound_mode is code.const.SoundMode.STYLE
        assert dev.state.eq_band_gains_tenths_db==code.eq_style.STYLE_PRESETS[preset]
    asyncio.run(run())


def test_style_failure_does_not_publish_requested_preset(code):
    async def run():
        dev,_=device_with_peer(code)
        dev._async_request=AsyncMock(side_effect=code.device.UltimeaCommandError('no echo'))
        with pytest.raises(code.device.UltimeaCommandError):
            await dev.async_set_style_preset('pop')
        assert dev.state.eq_band_gains_tenths_db is None
        assert dev.state.sound_mode is None
    asyncio.run(run())


def test_style_values_are_readonly_sensors_and_precise(code):
    dev,_=device_with_peer(code)
    dev._apply_custom_profile(8,code.eq_style.STYLE_PRESETS['bass'])
    s=code.sensor.UltimeaStyleBand(dev,0,31)
    assert s.native_value==5.5 and s.available
    assert s.extra_state_attributes['style_preset']=='bass'
    assert not hasattr(s,'async_set_native_value')
    dev._apply_sound_mode(1)
    assert not s.available and s.native_value is None
    assert dev.state.eq_band_gains_tenths_db is None


def test_unknown_modes_clear_style_values(code):
    dev,peer=device_with_peer(code)
    dev._apply_custom_profile(8,code.eq_style.STYLE_PRESETS['pop'])
    peer.rx(1,8,b'\x55')
    assert dev.state.sound_mode is None and dev.state.eq_profile_id is None


def test_power_off_clears_style_values(code):
    dev,peer=device_with_peer(code)
    dev._apply_custom_profile(8,code.eq_style.STYLE_PRESETS['pop'])
    peer.rx(2,9,b'\x00')
    assert dev.state.sound_mode is None and dev.state.eq_profile_id is None
    assert not code.button.UltimeaStyleButton(dev,'flat').available


def test_disconnect_invalidates_style_and_reconnect_resubscribes(code,monkeypatch):
    async def run():
        dev,peer=device_with_peer(code)
        await dev.async_set_sound_mode(code.const.SoundMode.STYLE)
        await dev.async_disconnect()
        assert dev.state.eq_band_gains_tenths_db is None
        assert dev.state.sound_mode is None
        fresh=Peer(code,dev,mode=8)
        monkeypatch.setattr(code.device,'establish_connection',AsyncMock(return_value=fresh))
        await dev.async_refresh_all()
        fresh.start_notify.assert_awaited_once()
        assert dev.state.sound_mode is code.const.SoundMode.STYLE
        assert dev.state.eq_band_gains_tenths_db==code.eq_style.STYLE_PRESETS['rock']
        assert any(g==0 and c==1 for g,c,_ in fresh.trace)
    asyncio.run(run())


@pytest.mark.parametrize('mode',[1,2,7,8])
def test_full_refresh_only_reads_freshly_active_profile(code,mode):
    async def run():
        dev,peer=device_with_peer(code,mode=mode)
        # Seed an obsolete cached Style to catch a background mode switch.
        dev._apply_custom_profile(8,code.eq_style.STYLE_PRESETS['pop'])
        await dev.async_refresh_state()
        writes=[r for r in peer.trace if r[:2]==(2,4)]
        assert writes==([(2,4,bytes([mode]))] if mode in (7,8) else [])
        assert {c for g,c,d in peer.trace if g==1} >= {6,7,8,10,12,13,14,15,23,24}
        if mode==8: assert dev.state.eq_profile_id==8
        if mode==7: assert dev.state.eq_profile_id==7
    asyncio.run(run())


def test_failed_mode_query_never_restores_cached_style(code):
    async def run():
        dev,peer=device_with_peer(code)
        dev._apply_custom_profile(8,code.eq_style.STYLE_PRESETS['pop'])
        peer.mode_reply=b''
        await dev.async_refresh_state()
        assert not any(r[:2]==(2,4) for r in peer.trace)
        assert dev.state.sound_mode is None
        assert dev.state.eq_band_gains_tenths_db is None
    asyncio.run(run())


def test_readonly_style_read_rechecks_mode_instead_of_using_cache(code):
    async def run():
        dev,peer=device_with_peer(code,mode=1)
        dev._apply_custom_profile(8,code.eq_style.STYLE_PRESETS['rock'])
        with pytest.raises(code.device.UltimeaCommandError):
            await dev.async_read_style(activate=False)
        assert not any(r[:2]==(2,4) for r in peer.trace)
    asyncio.run(run())


def test_custom_eq_write_cannot_replace_style(code):
    async def run():
        dev,peer=device_with_peer(code,mode=8)
        dev._apply_custom_profile(8,code.eq_style.STYLE_PRESETS['pop'])
        with pytest.raises(code.device.UltimeaCommandError):
            await dev.async_set_eq_band(0,10)
        assert not any(r[:2]==(2,4) for r in peer.trace)
    asyncio.run(run())


def test_custom_eq_write_preserves_nine_bands(code):
    async def run():
        dev,peer=device_with_peer(code,mode=7)
        gains=tuple(range(-5,5))
        peer.curves[7]=code.protocol.build_equalizer_payload(gains)
        await dev.async_set_eq_band(0,10)
        assert dev.state.eq_band_gains_tenths_db==(10,)+gains[1:]
        assert dev.state.eq_profile_id==7
    asyncio.run(run())


def test_concurrent_style_and_eq_operations_are_serialized(code):
    async def run():
        dev,peer=device_with_peer(code,mode=7)
        await asyncio.gather(dev.async_set_eq_band(0,10),dev.async_set_style_preset('pop'))
        assert peer.trace[-1]==(2,4,code.eq_style.build_style_payload('pop'))
        assert dev.state.eq_profile_id==8
    asyncio.run(run())


def test_concurrent_requests_wait_for_one_handshake(code):
    async def run():
        dev,peer=device_with_peer(code)
        await asyncio.gather(dev.async_query(1,7),dev.async_query(1,24))
        assert [r[:2] for r in peer.trace]==[(1,1),(0,1),(1,7),(1,24)]
    asyncio.run(run())


def test_failed_handshake_blocks_profile_commands(code):
    async def run():
        dev,peer=device_with_peer(code);peer.bad_safe=True
        with pytest.raises(code.device.UltimeaCommandError):
            await dev.async_set_style_preset('rock')
        assert not any(r[:2]==(2,4) for r in peer.trace)
        assert not dev._safe_code_authenticated
    asyncio.run(run())


def test_startup_does_not_query_until_post_start(code,monkeypatch):
    async def run():
        dev,peer=device_with_peer(code)
        def background(coro,*a,**k):
            coro.close()
            return None
        monkeypatch.setattr(dev,'_async_create_runtime_task',background)
        await dev.async_start()
        assert not peer.trace
        await dev.async_post_start()
        assert (0,0,b'') in peer.trace
        assert (1,24,b'') in peer.trace
        assert (2,4,b'\x08') in peer.trace
    asyncio.run(run())


def test_style_is_gated_to_verified_model(code):
    c=code.const
    generic=code.runtime.UltimeaDevice(SimpleNamespace(),'00:00:00:00:00:02','Generic')
    generic.identity.model='Unverified model';generic.restore_capabilities()
    assert not generic.supports(c.Feature.STYLE)
    async def run():
        with pytest.raises(code.device.UltimeaCommandError):
            await generic.async_set_style_preset('rock')
        with pytest.raises(code.device.UltimeaCommandError):
            await generic.async_set_sound_mode(c.SoundMode.STYLE)
    asyncio.run(run())


def test_new_entity_counts_and_dynamic_style_badge(code):
    async def run():
        dev,peer=device_with_peer(code)
        entry=SimpleNamespace(runtime_data=SimpleNamespace(device=dev))
        buttons=[];sensors=[]
        await code.button.async_setup_entry(None,entry,buttons.extend)
        await code.sensor.async_setup_entry(None,entry,sensors.extend)
        assert len(buttons)==5 and len(sensors)==11
        assert len({e._attr_unique_id for e in buttons+sensors})==16
        await dev.async_set_style_preset('classical')
        player=code.media_player.UltimeaMediaPlayer(dev,100)
        assert 'Style' in player.sound_mode_list
        assert player.sound_mode=='Style'
        assert player.extra_state_attributes['style_preset']=='classical'
        from urllib.parse import unquote
        assert '>STY<' in unquote(player.entity_picture)
        assert not code.number.UltimeaEqualizerBand(dev,0,31).available
    asyncio.run(run())


def test_style_translations_and_changelogs_match():
    names={'style_reset','style_bass','style_rock','style_pop','style_classical'}
    for path in [COMPONENT/'strings.json',*(COMPONENT/'translations').glob('*.json')]:
        data=json.loads(path.read_text())['entity']
        assert names <= data['button'].keys()
        assert '{frequency}' in data['sensor']['style_band']['name']
    assert (ROOT/'CHANGELOG.md').read_bytes()==(COMPONENT/'CHANGELOG.md').read_bytes()
