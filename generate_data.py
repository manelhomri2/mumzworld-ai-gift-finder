import json
import random


categories = [
"Baby Care",
"Toys",
"Clothing",
"Feeding",
"Safety",
"Learning",
"Health"
]


ages=[
"0-6 months",
"6-12 months",
"1-3 years",
"3-5 years"
]


products=[]


for i in range(300):

    category=random.choice(categories)
    age=random.choice(ages)
    price=random.randint(20,500)


    products.append({

        "id":i,

        "name":
        f"{category} Product {i}",

        "category":category,

        "age":age,

        "price":price,


        "description":
        f"""
        High quality {category}
        product suitable for children
        aged {age}.
        Perfect gift option for moms.
        """
    })


with open(
"data/products.json",
"w",
encoding="utf-8"
) as f:

    json.dump(
        products,
        f,
        indent=2,
        ensure_ascii=False
    )


print("Dataset created")