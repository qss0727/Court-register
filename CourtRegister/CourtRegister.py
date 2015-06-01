from json import dumps
from neo4jrestclient.client import GraphDatabase
from flask import Flask, Response, request, render_template
from datetime import datetime
from re import findall

app = Flask(__name__, static_url_path='/static/')
gdb = GraphDatabase("http://localhost:7474")


@app.route('/test')
def test():
    return render_template("test.html")


def __timestamp__(_datetime):
    if _datetime is not None and _datetime != '' and not isinstance(_datetime, float):
        d = [int(x) for x in findall(r'\d+', _datetime)]
        return datetime(d[2], d[1], d[0], 0, 0, 0).timestamp()
    else:
        return _datetime


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        neo4j_query = query_builder(request.form)
        nodes, rels = generate_graph(25)
        js = dumps({"nodes": nodes, "edges": rels})
        # print(js)
        return render_template('index.html', json=js)
    else:
        neo4j_query = query_builder(request.form)
        # print(request.form)
        nodes, rels = generate_graph(25, neo4j_query)
        js = dumps({"nodes": nodes, "edges": rels})
        print(js)
        # print(neo4j_query)
        return render_template('index.html', json=js)
        # return Response(neo4j_query)


def where_builder(params):
    try:
        result = 'WHERE '
        query_list = []
        if params['region']:
            query_list.append('(r.name =~ ".*' + params['region'] + '.*") ')
        if params['court']:
            query_list.append('(crt.name =~ ".*' + params['court'] + '.*") ')
        if params['chairman']:
            query_list.append('(ch.name =~ ".*' + params['chairman'] + '.*") ')
        # TODO
        if params['dateFrom']:
            timestamp = __timestamp__(params['dateFrom'])
            if timestamp != '':
                query_list.append('(toFloat(c.law_date) >= ' + str(timestamp) + ') ')
        if params['dateTo']:
            timestamp = __timestamp__(params['dateTo'])
            if timestamp != '':
                query_list.append('(toFloat(c.law_date) <= ' + str(timestamp) + ') ')
        # /TODO
        if 'caseTypes' in params:
            case_type_list = []
            s = '('
            for c in params.getlist('caseTypes'):
                case_type_list.append('vt.name = "' + c + '"')
            if len(case_type_list) > 1:
                for c in case_type_list[:-1]:
                    s += c + ' OR '
                s += case_type_list[len(case_type_list) - 1] + ')'
            if len(case_type_list) > 0:
                query_list.append(s)
        if len(query_list) > 1:
            for s in query_list[:-1]:
                result += s + 'AND '
            result += query_list[len(query_list) - 1]
        elif len(query_list) == 1:
            result += query_list[0]
        else:
            return ''
    except BaseException as e:
        result = ''
    return result


def query_builder(where_dict=None, limit=10, order=None):
    final_query = query_base
    if where_dict:
        final_query += where_builder(where_dict)
    final_query += query_return
    if order:
        final_query += 'ORDER BY ' + order + ' '
    final_query += 'LIMIT ' + str(limit)
    return final_query


query_base = """
MATCH (r:Region)<-[crt_r:SITUATED_IN]-(crt:Court)<-[c_crt:RULED_BY]-(c:Case)-[c_ch:CARRIED_BY]->(ch:Chairman),
(ct:Court_Decision_Type)-[c_ct]-c-[c_vt]-(vt:Court_Judgement_Type)
"""
query_return = """
RETURN r, crt, c, ch, ct, vt, crt_r, c_crt, c_ch, c_ct, c_vt
"""

query_sample = """
match (r:Region)<-[crt_r:SITUATED_IN]-(crt:Court)<-[c_crt:RULED_BY]-(c:Case)-[c_ch:CARRIED_BY]->(ch:Chairman),
(ct:Court_Decision_Type)-[c_ct]-c-[c_vt]-(vt:Court_Judgement_Type)
where r.name='Київська область'
return r, crt, c, ch, ct, vt, c_crt
order by vt.name
limit 10
"""


def node(title, label, _id, cluster, ids):
    return {'caption': title, 'node_type': label, 'id': ids[_id], 'cluster': cluster}


def relation(rel, ids, cluster):
    start = int(rel['start'].split('/')[-1])
    end = int(rel['end'].split('/')[-1])
    # print([start, end])
    _type = rel['metadata']['type']
    return {'source': ids[start], 'target': ids[end], 'caption': _type, 'cluster': cluster}


@app.route("/graph")
def get_graph():
    nodes, rels = generate_graph(25)
    s = dumps({"nodes": nodes, "edges": rels})
    try:
        return Response(s, mimetype="application/json")
    except BaseException as e:
        print(e.__str__())
        return Response(dumps({'error: ': e.__str__()}))


def generate_graph(limit=25, query=None):
    def manage_id(_i, _id, _dict):
        if _id not in _dict:
            _dict[_id] = _id
        return _i, _id

    query = query or query_builder()
    results = gdb.query(query, params={"limit": limit})
    nodes, rels = [], []
    ids_dict = {}
    i = 0
    for region, court, case, chairman, ct, vt, crt_r, c_crt, c_ch, c_ct, c_vt in results:
        i, __id = manage_id(i, region['metadata']['id'], ids_dict)
        reg_node = node(region['data']['name'], 'Region', region['metadata']['id'], 1, ids_dict)
        if reg_node not in nodes:
            nodes.append(reg_node)
        # court
        i, __id = manage_id(i, court['metadata']['id'], ids_dict)
        court_node = node(court['data']['name'], 'Court', court['metadata']['id'], 2, ids_dict)
        if court_node not in nodes:
            nodes.append(court_node)
        # chairman
        i, __id = manage_id(i, chairman['metadata']['id'], ids_dict)
        chairman_node = node(chairman['data']['name'], 'Chairman', chairman['metadata']['id'], 3, ids_dict)
        if chairman_node not in nodes:
            nodes.append(chairman_node)
        # ct
        i, __id = manage_id(i, ct['metadata']['id'], ids_dict)
        ct_node = node(ct['data']['name'], 'Court Decision Type', ct['metadata']['id'], 4, ids_dict)
        if ct_node not in nodes:
            nodes.append(ct_node)
        # vt
        i, __id = manage_id(i, vt['metadata']['id'], ids_dict)
        vt_node = node(vt['data']['name'], 'Court Judgement Type', vt['metadata']['id'], 5, ids_dict)
        if vt_node not in nodes:
            nodes.append(vt_node)
        # case
        # TODO: INFO!!!1
        i, __id = manage_id(i, case['metadata']['id'], ids_dict)
        case_node = node('№' + case['data']['case_number'], 'Court case', case['metadata']['id'], 6, ids_dict)
        if case_node not in nodes:
            nodes.append(case_node)
        # crt_r
        crt_r_rel = relation(crt_r, ids_dict, 7)
        if crt_r_rel not in rels:
            rels.append(crt_r_rel)
        # c_crt
        c_crt_rel = relation(c_crt, ids_dict, 8)
        if c_crt_rel not in rels:
            rels.append(c_crt_rel)
        # c_ch
        c_ch_rel = relation(c_ch, ids_dict, 9)
        if c_ch_rel not in rels:
            rels.append(c_ch_rel)
        # c_ct
        c_ct_rel = relation(c_ct, ids_dict, 10)
        if c_ct_rel not in rels:
            rels.append(c_ct_rel)
        # c_vt
        c_vt_rel = relation(c_vt, ids_dict, 11)
        if c_vt_rel not in rels:
            rels.append(c_vt_rel)
    return nodes, rels

# original:
#
# def generate_graph(limit=25):
#     query = query_builder()
#     results = gdb.query(query,
#                         params={"limit": limit})
#     nodes = []
#     rels = []
#     ids_dict = {}
#     i = 0
#     for region, court, case, chairman, ct, vt, crt_r, c_crt, c_ch, c_ct, c_vt in results:
#         # region
#         reg_node = node(region['data']['name'], 'Region', region['metadata']['id'], 1)
#         if reg_node not in nodes:
#             nodes.append(reg_node)
#         # court
#         court_node = node(court['data']['name'], 'Court', court['metadata']['id'], 2)
#         if court_node not in nodes:
#             nodes.append(court_node)
#         # chairman
#         chairman_node = node(chairman['data']['name'], 'Chairman', chairman['metadata']['id'], 3)
#         if chairman_node not in nodes:
#             nodes.append(chairman_node)
#         # ct
#         ct_node = node(ct['data']['name'], 'Court Decision Type', ct['metadata']['id'], 4)
#         if ct_node not in nodes:
#             nodes.append(ct_node)
#         # vt
#         vt_node = node(vt['data']['name'], 'Court Judgement Type', vt['metadata']['id'], 5)
#         if vt_node not in nodes:
#             nodes.append(vt_node)
#         # case
#         # TODO: INFO!!!1
#         case_node = node('№' + case['data']['case_number'], 'Court case', case['metadata']['id'], 6)
#         if case_node not in nodes:
#             # print(case['data'])
#             nodes.append(case_node)
#         # crt_r
#         crt_r_rel = relation(crt_r, 7)
#         if crt_r_rel not in rels:
#             rels.append(crt_r_rel)
#         # c_crt
#         c_crt_rel = relation(c_crt, 8)
#         if c_crt_rel not in rels:
#             rels.append(c_crt_rel)
#         # c_ch
#         c_ch_rel = relation(c_ch, 9)
#         if c_ch_rel not in rels:
#             rels.append(c_ch_rel)
#         # c_ct
#         c_ct_rel = relation(c_ct, 10)
#         if c_ct_rel not in rels:
#             rels.append(c_ct_rel)
#         # c_vt
#         c_vt_rel = relation(c_vt, 11)
#         if c_vt_rel not in rels:
#             rels.append(c_vt_rel)
#     return nodes, rels


if __name__ == '__main__':
    app.run()
