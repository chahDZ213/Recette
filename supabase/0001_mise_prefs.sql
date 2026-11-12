-- mise. — courses, « ma liste » et menu de la semaine rattachés au compte
--
-- Jusqu'ici ces trois contenus ne vivaient qu'en localStorage : un changement
-- de téléphone les perdait, alors que les recettes suivaient le compte. Pour
-- un abonnement payant, c'est une promesse rompue.
--
-- Une seule ligne par compte, un seul document JSON. Chaque clé y porte sa
-- propre date de modification, pour que modifier les courses sur un téléphone
-- et le menu sur un autre ne fasse pas disparaître l'un des deux :
--
--   {
--     "mise_shopping":      { "v": "[…]", "maj": 1763000000000 },
--     "mise_shopping_note": { "v": "…",   "maj": 1763000000000 },
--     "mise_week":          { "v": "{…}", "maj": 1763000000000 }
--   }
--
-- Volontairement absents : thème, couleur d'accent, fond, langue, dernière vue.
-- Ce sont des réglages d'appareil — un téléphone en sombre et un ordinateur en
-- clair est un choix, pas une anomalie à réparer.
--
-- À appliquer dans Supabase → SQL Editor du projet mise.
-- Rejouable sans dommage.

create table if not exists public.mise_prefs (
  user_id uuid primary key references auth.users(id) on delete cascade,
  donnees jsonb        not null default '{}'::jsonb,
  maj_at  timestamptz  not null default now()
);

comment on table public.mise_prefs is
  'Contenus de mise. rattachés au compte : liste de courses, note libre, menu de la semaine. Un document JSON par compte, chaque clé horodatée.';

alter table public.mise_prefs enable row level security;

-- Chacun ne lit et n'écrit que sa propre ligne. La clé service_role, elle,
-- ignore la RLS : c'est par elle que passe l'effacement du compte.
drop policy if exists "mise_prefs_select_self" on public.mise_prefs;
create policy "mise_prefs_select_self" on public.mise_prefs
  for select using (auth.uid() = user_id);

drop policy if exists "mise_prefs_insert_self" on public.mise_prefs;
create policy "mise_prefs_insert_self" on public.mise_prefs
  for insert with check (auth.uid() = user_id);

drop policy if exists "mise_prefs_update_self" on public.mise_prefs;
create policy "mise_prefs_update_self" on public.mise_prefs
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "mise_prefs_delete_self" on public.mise_prefs;
create policy "mise_prefs_delete_self" on public.mise_prefs
  for delete using (auth.uid() = user_id);
