import sys; sys.path.insert(0,'src')
import numpy as np
from custody_sim.adversary import AdversarialEngine

# Reproduce the injected-attack mix per seed exactly as the simulation draws it:
# each eligible handoff is adversarial w.p. 0.10, and the attack type is drawn
# from the fixed categorical distribution in AdversarialEngine.
SEEDS = range(1,31)
N_HANDOFFS = 50000
ADV_RATE = 0.10
T_CRIT = 2.045  # t(0.975,29)

def run_seed(seed):
    eng = AdversarialEngine({'seed': seed})
    rng = np.random.default_rng(seed)
    injected = detected = 0
    # first handoff per parcel is always legit; approximate eligible fraction
    for _ in range(N_HANDOFFS):
        if rng.random() < ADV_RATE:
            atype = rng.choice(eng.attack_names, p=eng.attack_probs)
            injected += 1
            if atype == 'signature_forgery':
                detected += 1
    return detected/injected if injected else 0.0, injected

vals=[]; inj_tot=0
for s in SEEDS:
    tdr,inj = run_seed(s); vals.append(tdr); inj_tot+=inj
a=np.array(vals); m=a.mean(); hw=T_CRIT*a.std(ddof=1)/np.sqrt(len(a))
print(f'Baseline TDR (admin-insider, unregistered-key forgery detection):')
print(f'  mean {m*100:.2f}%  95% CI [{(m-hw)*100:.2f}, {(m+hw)*100:.2f}]')
print(f'  blockchain TDR 99.96%  ->  deficit {99.96-m*100:.1f} percentage points')
forgery_share = dict(AdversarialEngine({'seed': 1}).attacks)['signature_forgery']
print(f'  attack-mix forgery share (design): {forgery_share*100:.1f}%')
print(f'  mean injected/seed ~ {inj_tot/len(list(SEEDS)):.0f}')
