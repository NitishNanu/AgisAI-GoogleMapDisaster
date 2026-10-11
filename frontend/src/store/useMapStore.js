import { create } from 'zustand';

export const useMapStore = create((set, get) => ({
    citizens: new Map(),
    buildings: new Map(),
    fleet: new Map(),
    incidents: new Map(),

    // Initialize full state
    setFullState: (state) => set({
        citizens: new Map(state.citizens?.map(c => [c.id, c])),
        buildings: new Map(state.buildings?.map(b => [b.id, b])),
        fleet: new Map(state.fleet?.map(f => [f.id, f])),
        incidents: new Map(state.incidents?.map(i => [i.id, i]))
    }),

    // Process deltas to prevent full re-renders
    applyDeltas: (deltas) => set((state) => {
        const newCitizens = new Map(state.citizens);
        const newBuildings = new Map(state.buildings);
        const newFleet = new Map(state.fleet);
        const newIncidents = new Map(state.incidents);

        deltas.citizens?.forEach(c => newCitizens.set(c.id, { ...newCitizens.get(c.id), ...c }));
        deltas.buildings?.forEach(b => newBuildings.set(b.id, { ...newBuildings.get(b.id), ...b }));
        deltas.fleet?.forEach(f => newFleet.set(f.id, { ...newFleet.get(f.id), ...f }));
        deltas.incidents?.forEach(i => newIncidents.set(i.id, { ...newIncidents.get(i.id), ...i }));

        return {
            citizens: newCitizens,
            buildings: newBuildings,
            fleet: newFleet,
            incidents: newIncidents
        };
    })
}));

export default useMapStore;
