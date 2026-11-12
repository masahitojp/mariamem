"""Use the existing native/two-child owner, adding five encodings and variant order."""
import uca_prepared_acceptance as owner


def profiles(c):
    result = {}
    encodings = ['utf8mb3', 'utf8mb4', 'ucs2', 'utf16', 'utf32']
    for order in (encodings, list(reversed(encodings))):
        for encoding in order:
            # Alternate variant/default operation order. This is query order,
            # not proof of lazy internal initialization order.
            variants = ['as_cs', 'ai_ci'] if order is encodings else ['ai_ci', 'as_cs']
            for suffix in variants:
                coll = encoding+'_uca1400_'+suffix
                left = f"CONVERT(_utf8mb4'ch' USING {encoding}) COLLATE {coll}"
                right = f"CONVERT(_utf8mb4'cH' USING {encoding}) COLLATE {coll}"
                row = owner.query(c, f'SELECT STRCMP({left},{right}),HEX(WEIGHT_STRING({left}))')
                if coll in result:
                    assert result[coll] == row, 'operation order changed collation result'
                result[coll] = row
    result['generic_alias'] = owner.query(c, "SELECT STRCMP(_utf8mb4'ch' COLLATE uca1400_ai_ci,_utf8mb4'cH' COLLATE utf8mb4_uca1400_ai_ci)")
    return result


semantic = owner.semantic
observations = owner.observations


def extended_semantic(c):
    result = semantic(c)
    result['uca_copy_profiles'] = profiles(c)
    return result


def extended_observations(c):
    result = observations(c)
    result['uca_copy_profiles'] = profiles(c)
    import json
    return json.loads(json.dumps(result))


if __name__ == '__main__':
    owner.semantic = extended_semantic
    owner.observations = extended_observations
    owner.main()
