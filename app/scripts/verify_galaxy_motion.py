"""Optional browser QA for an already-running app; requires Playwright + Chromium.

Does not upload, delete, configure sources, or export browser capabilities.
Usage: python scripts/verify_galaxy_motion.py --base-url http://127.0.0.1:8000 --output-dir .cache/galaxy-qa
"""
from __future__ import annotations

import argparse
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

SNAPSHOT = """els => Object.fromEntries(els.map(e => [e.dataset.nodeId, e.getAttribute('transform')]))"""
GEOMETRY = """() => {
 const point = e => (e.getAttribute('transform').match(/-?\\d+(?:\\.\\d+)?/g)||[]).map(Number);
 const nodes = new Map(Array.from(document.querySelectorAll('.graph-node')).map(e=>[e.dataset.nodeId,point(e)]));
 let tested=0;
 for (const edge of document.querySelectorAll('.graph-edge')) {
  const paths=Array.from(edge.querySelectorAll('path'));
  if(paths.length!==2||paths[0].getAttribute('d')!==paths[1].getAttribute('d')) return {ok:false,reason:'visible/hit-area mismatch'};
  const curve=paths[0].getAttribute('d').match(/-?\\d+(?:\\.\\d+)?/g).map(Number);
  const source=nodes.get(edge.dataset.sourceId),target=nodes.get(edge.dataset.targetId);
  if(!source||!target) return {ok:false,reason:'missing node'};
  if(Math.abs(curve[0]-source[0])>.002||Math.abs(curve[1]-source[1])>.002||Math.abs(curve[4]-target[0])>.002||Math.abs(curve[5]-target[1])>.002) return {ok:false,reason:'endpoint mismatch'};
  tested++;
 }
 return {ok:tested>0,edges:tested};
}"""
HITTABLE = """type => {
 for(const e of document.querySelectorAll('.graph-node')) {
  if(type ? e.dataset.nodeType!==type : e.dataset.nodeType==='workspace') continue;
  const p=new DOMPoint(0,0).matrixTransform(e.getScreenCTM());
  if(p.x<5||p.y<5||p.x>innerWidth-5||p.y>innerHeight-5)continue;
  if(document.elementFromPoint(p.x,p.y)?.closest('.graph-node')===e)
   return {id:e.dataset.nodeId,x:p.x,y:p.y,label:e.querySelector('title').textContent};
 }
 return null;
}"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--output-dir', type=Path, default=Path('.cache/galaxy-qa'))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'environment': 'Playwright Chromium / ' + platform.system(),
              'windows_cmd_launcher_tested': False, 'checks': [], 'page_errors': [], 'viewports': []}

    def passed(name, **details):
        report['checks'].append({'name': name, 'status': 'passed', **details})
        print('PASS:', name, flush=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
        report['browser_version'] = browser.version
        context = browser.new_context(viewport={'width': 1440, 'height': 1050}, reduced_motion='no-preference')
        page = context.new_page()
        page.set_default_timeout(8000)
        page.on('pageerror', lambda error: report['page_errors'].append(str(error)))
        stage = page.locator('.galaxy-stage')
        nodes = page.locator('.graph-node')

        def snapshot():
            return nodes.evaluate_all(SNAPSHOT)

        def still():
            page.wait_for_timeout(120)
            first = snapshot()
            page.wait_for_timeout(550)
            assert first == snapshot(), 'Geometry moved while it should be frozen.'

        def moving():
            first = snapshot()
            page.wait_for_timeout(850)
            second = snapshot()
            changed = sum(first[key] != second[key] for key in first if key in second)
            assert changed > 0, 'No entity movement detected.'
            return changed

        def node_transform(node_id):
            return page.evaluate("id=>Array.from(document.querySelectorAll('.graph-node')).find(e=>e.dataset.nodeId===id).getAttribute('transform')", node_id)

        try:
            page.goto(args.base_url, wait_until='networkidle')
            page.wait_for_selector('.graph-node[data-node-type="signal"]')
            page.evaluate('document.fonts.ready')
            expect(stage).to_have_attribute('data-motion', 'running')
            page.mouse.move(0, 0)
            core = page.locator('.graph-node[data-node-type="workspace"]').get_attribute('transform')
            changed = moving()
            assert core == page.locator('.graph-node[data-node-type="workspace"]').get_attribute('transform')
            passed('Actual entities move; workspace remains anchored', nodes=nodes.count(), moving_nodes=changed)

            geometry = page.evaluate(GEOMETRY)
            assert geometry['ok'], geometry
            passed('All visible curves and hit areas follow their real node endpoints', edges=geometry['edges'])
            page.screenshot(path=str(args.output_dir / 'galaxy-desktop.png'), full_page=True)

            page.get_by_role('button', name='Jeda animasi galaksi', exact=True).click()
            expect(stage).to_have_attribute('data-motion', 'paused')
            still()
            held = snapshot()
            page.get_by_label('Sorot jenis entitas', exact=True).select_option('source')
            assert held == snapshot(), 'Filtering changed the paused pose.'
            passed('Pause freezes geometry even through filter re-renders')

            page.reload(wait_until='networkidle')
            page.wait_for_selector('.graph-node[data-node-type="signal"]')
            expect(stage).to_have_attribute('data-motion', 'paused')
            expect(page.get_by_role('button', name='Aktifkan animasi galaksi', exact=True)).to_have_attribute('aria-pressed', 'false')
            still()
            passed('Pause preference survives page reload')
            page.get_by_role('button', name='Aktifkan animasi galaksi', exact=True).click()
            expect(stage).to_have_attribute('data-motion', 'running')
            moving()
            passed('Resume restarts motion')

            candidate = page.evaluate(HITTABLE, 'source') or page.evaluate(HITTABLE, None)
            assert candidate, 'No hittable entity.'
            page.mouse.move(candidate['x'], candidate['y'])
            page.wait_for_timeout(150)
            held = node_transform(candidate['id'])
            page.wait_for_timeout(600)
            assert held == node_transform(candidate['id']), 'Hovered entity did not freeze.'
            moving()
            passed('Hover holds the target while other entities continue moving')
            page.mouse.click(candidate['x'], candidate['y'])
            expect(page.locator('.entity-body h4')).to_have_text(candidate['label'])
            page.mouse.move(0, 0)
            held = node_transform(candidate['id'])
            page.wait_for_timeout(550)
            assert held == node_transform(candidate['id'])
            passed('Moving entity can be clicked and stays fixed while selected')

            target = page.locator('.graph-node[data-node-type="signal"]').first
            label = target.locator('title').text_content()
            target.focus()
            held = target.get_attribute('transform')
            page.wait_for_timeout(550)
            assert held == target.get_attribute('transform'), 'Focused entity moved.'
            target.press('Enter')
            expect(page.locator('.entity-body h4')).to_have_text(label)
            passed('Keyboard focus freezes entities and Enter opens real entity details')

            page.get_by_role('button', name='Perbesar', exact=True).click()
            expect(page.locator('.graph-controls>span')).to_have_text('115%')
            page.get_by_role('button', name='Atur ulang posisi', exact=True).click()
            expect(page.locator('.graph-controls>span')).to_have_text('100%')
            before = page.locator('.graph-universe').get_attribute('transform')
            box = stage.bounding_box()
            page.mouse.move(box['x'] + 8, box['y'] + 12)
            page.mouse.down()
            page.mouse.move(box['x'] + 38, box['y'] + 27, steps=4)
            page.mouse.up()
            assert page.locator('.graph-universe').get_attribute('transform') != before
            page.get_by_role('button', name='Atur ulang posisi', exact=True).click()
            assert page.locator('.graph-universe').get_attribute('transform') == before
            assert page.evaluate(GEOMETRY)['ok']
            passed('Zoom, pan and reset preserve connected geometry')

            page.get_by_role('button', name='Perbesar galaksi', exact=True).click()
            expect(page.locator('.galaxy-fullscreen')).to_be_visible()
            page.wait_for_timeout(300)
            assert page.evaluate(GEOMETRY)['ok']
            moving()
            page.keyboard.press('Escape')
            expect(page.locator('.galaxy-fullscreen')).to_have_count(0)
            passed('Fullscreen motion and Escape work with connected geometry')

            page.emulate_media(reduced_motion='reduce')
            expect(stage).to_have_attribute('data-motion', 'reduced')
            expect(page.get_by_role('button', name='Animasi mengikuti pengaturan kurangi gerakan', exact=True)).to_be_disabled()
            still()
            page.emulate_media(reduced_motion='no-preference')
            expect(stage).to_have_attribute('data-motion', 'running')
            moving()
            passed('Reduced-motion OS preference stops animation and restores safely')

            # Simulate a visibility event; the app must stop its RAF work without resetting poses.
            page.evaluate("Object.defineProperty(document,'hidden',{get:()=>true,configurable:true});document.dispatchEvent(new Event('visibilitychange'))")
            expect(stage).to_have_attribute('data-motion', 'offscreen')
            still()
            page.evaluate("delete document.hidden;document.dispatchEvent(new Event('visibilitychange'))")
            expect(stage).to_have_attribute('data-motion', 'running')
            moving()
            passed('Hidden-document visibility event stops and resumes motion')

            page.set_viewport_size({'width': 1440, 'height': 360})
            page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)')
            expect(stage).to_have_attribute('data-motion', 'offscreen')
            still()
            page.evaluate('window.scrollTo(0,0)')
            stage.scroll_into_view_if_needed()
            expect(stage).to_have_attribute('data-motion', 'running')
            moving()
            passed('Offscreen galaxy suspends animation until visible again')

            for width in (340, 390, 768, 1024, 1440):
                page.set_viewport_size({'width': width, 'height': 980})
                page.evaluate('window.scrollTo(0,0)')
                page.wait_for_timeout(150)
                overflow = page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
                assert not overflow, f'Horizontal overflow at {width}px.'
                assert page.evaluate(GEOMETRY)['ok']
                report['viewports'].append({'width': width, 'horizontal_overflow': False, 'edges_connected': True})
                if width == 390:
                    page.screenshot(path=str(args.output_dir / 'galaxy-mobile.png'), full_page=True)
            passed('Responsive controls and connected edges at 340/390/768/1024/1440px')

            # Existing simulation and empty private-workspace states still work.
            page.get_by_role('button', name='Simulasi', exact=True).click()
            expect(page.locator('.demo-notice')).to_be_visible()
            expect(nodes.nth(1)).to_be_visible()
            expect(stage).to_have_attribute('data-motion', 'running')
            moving()
            assert page.evaluate(GEOMETRY)['ok']
            with page.expect_response(lambda response: '/api/graph?dataset=live' in response.url and response.status == 200):
                page.get_by_role('button', name='Data saya', exact=True).click()
            expect(stage).to_have_attribute('data-motion', 'empty')
            expect(page.get_by_role('button', name='Jeda animasi galaksi', exact=True)).to_be_disabled()
            page.get_by_role('button', name='Data eksternal', exact=True).click()
            page.wait_for_selector('.graph-node[data-node-type="signal"]')
            expect(stage).to_have_attribute('data-motion', 'running')
            passed('Simulation and empty private workspace stay separate and usable')

            assert not report['page_errors'], report['page_errors']
            passed('Zero JavaScript page errors')
            report['status'] = 'passed'
        except Exception as error:
            report['status'] = 'failed'
            report['failure'] = str(error)
            page.screenshot(path=str(args.output_dir / 'failure.png'), full_page=True)
            raise
        finally:
            report['passed_checks'] = len(report['checks'])
            (args.output_dir / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
            context.close()
            browser.close()
    print(json.dumps({'status':report['status'], 'passed_checks':report['passed_checks'], 'page_errors':len(report['page_errors'])}))


if __name__ == '__main__':
    main()
