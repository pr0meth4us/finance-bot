from datetime import datetime
from zoneinfo import ZoneInfo

PHNOM_PENH_TZ = ZoneInfo("Asia/Phnom_Penh")

FINANCIAL_TRANSACTION_CATEGORIES = [
    'Loan Lent', 'Debt Repayment', 'Loan Received', 'Debt Settled', 'Initial Balance'
]


def get_currency_conversion_stage(user_rate):
    """Returns the $addFields stage for converting amounts to USD."""
    return {
        '$addFields': {
            'amount_in_usd': {
                '$cond': {
                    'if': {'$eq': ['$currency', 'USD']},
                    'then': '$amount',
                    'else': {
                        '$divide': [
                            '$amount',
                            {
                                '$cond': {
                                    'if': {'$gt': [{'$ifNull': ['$exchangeRateAtTime', user_rate]}, 0]},
                                    'then': {'$ifNull': ['$exchangeRateAtTime', user_rate]},
                                    'else': user_rate
                                }
                            }
                        ]
                    }
                }
            }
        }
    }


def build_search_pipeline(match_stage):
    """Builds the pipeline for transaction search analytics."""
    return [
        {'$match': match_stage},
        {
            '$group': {
                '_id': '$currency',
                'totalAmount': {'$sum': '$amount'},
                'count': {'$sum': 1},
                'minAmount': {'$min': '$amount'},
                'maxAmount': {'$max': '$amount'},
                'minDate': {'$min': '$timestamp'},
                'maxDate': {'$max': '$timestamp'}
            }
        }
    ]


def build_start_balance_pipeline(start_date_utc, user_match, user_rate):
    """Calculates income and expenses prior to the start date."""
    return [
        {'$match': {'timestamp': {'$lt': start_date_utc}, **user_match}},
        get_currency_conversion_stage(user_rate),
        {'$group': {'_id': '$type', 'totalUSD': {'$sum': '$amount_in_usd'}}}
    ]


def build_faceted_report_pipeline(date_range_match, user_match, user_rate):
    """Combines multiple analytical views into a single $facet aggregation."""
    conversion_stage = get_currency_conversion_stage(user_rate)
    base_match = {**date_range_match, **user_match}

    non_financial_match = {'type': 'expense', 'categoryId': {'$nin': FINANCIAL_TRANSACTION_CATEGORIES}}

    return [
        {'$match': base_match},
        conversion_stage,
        {
            '$facet': {
                'operational': [
                    {'$match': {'categoryId': {'$nin': FINANCIAL_TRANSACTION_CATEGORIES}}},
                    {'$group': {'_id': {'type': '$type', 'category': '$categoryId'},
                                'total': {'$sum': '$amount_in_usd'}}},
                    {'$sort': {'total': -1}}
                ],
                'financial': [
                    {'$match': {'categoryId': {'$in': FINANCIAL_TRANSACTION_CATEGORIES}}},
                    {'$group': {'_id': '$categoryId', 'total': {'$sum': '$amount_in_usd'}}}
                ],
                'total_flow': [
                    {'$group': {'_id': '$type', 'totalUSD': {'$sum': '$amount_in_usd'}}}
                ],
                'spending_over_time': [
                    {'$match': non_financial_match},
                    {
                        '$project': {
                            'date': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$timestamp',
                                                       'timezone': 'Asia/Phnom_Penh'}},
                            'amount_in_usd': 1
                        }
                    },
                    {'$group': {'_id': '$date', 'total_spent_usd': {'$sum': '$amount_in_usd'}}},
                    {'$sort': {'_id': 1}},
                    {'$project': {'_id': 0, 'date': '$_id', 'total_spent_usd': 1}}
                ],
                'daily_stats': [
                    {'$match': non_financial_match},
                    {
                        '$group': {
                            '_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$timestamp',
                                                      'timezone': 'Asia/Phnom_Penh'}},
                            'total_spent_usd': {'$sum': '$amount_in_usd'}
                        }
                    },
                    {'$sort': {'total_spent_usd': -1}}
                ],
                'top_expense': [
                    {'$match': non_financial_match},
                    {'$sort': {'amount_in_usd': -1}},
                    {'$limit': 1},
                    {
                        '$project': {
                            '_id': 0,
                            'description': '$description',
                            'category': '$categoryId',
                            'amount_usd': '$amount_in_usd',
                            'date': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$timestamp',
                                                       'timezone': 'Asia/Phnom_Penh'}}
                        }
                    }
                ]
            }
        }
    ]


def build_habits_pipeline(start_date_utc, end_date_utc, user_match, user_rate):
    """Pipelines for spending habits (Day of Week, Keywords)."""
    conversion_stage = get_currency_conversion_stage(user_rate)
    match_base = {
        'timestamp': {'$gte': start_date_utc, '$lte': end_date_utc},
        'type': 'expense',
        **user_match
    }

    day_of_week = [
        {'$match': match_base},
        conversion_stage,
        {'$group': {
            '_id': {'$dayOfWeek': {'date': '$timestamp', 'timezone': 'Asia/Phnom_Penh'}},
            'totalAmount': {'$sum': '$amount_in_usd'}
        }},
        {'$sort': {'_id': 1}},
        {'$project': {
            '_id': 0,
            'day': {'$switch': {'branches': [
                {'case': {'$eq': ["$_id", 1]}, 'then': 'Sunday'},
                {'case': {'$eq': ["$_id", 2]}, 'then': 'Monday'},
                {'case': {'$eq': ["$_id", 3]}, 'then': 'Tuesday'},
                {'case': {'$eq': ["$_id", 4]}, 'then': 'Wednesday'},
                {'case': {'$eq': ["$_id", 5]}, 'then': 'Thursday'},
                {'case': {'$eq': ["$_id", 6]}, 'then': 'Friday'},
                {'case': {'$eq': ["$_id", 7]}, 'then': 'Saturday'}
            ]}},
            'total': '$totalAmount'
        }}
    ]

    keywords = [
        {'$match': {**match_base, 'description': {'$exists': True, '$ne': ''}}},
        {'$group': {
            '_id': {'category': '$categoryId', 'keyword': {'$toLower': '$description'}},
            'count': {'$sum': 1}
        }},
        {'$sort': {'count': -1}},
        {'$group': {
            '_id': '$_id.category',
            'topKeywordsWithCount': {'$push': {'keyword': '$_id.keyword', 'count': '$count'}}
        }},
        {'$project': {
            '_id': 0,
            'category': '$_id',
            'topKeywords': {'$slice': ['$topKeywordsWithCount.keyword', 3]}
        }}
    ]

    return day_of_week, keywords