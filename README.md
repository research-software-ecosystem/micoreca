# Microbiome Community Resource Catalogue (MiCoReCa)

The rapid growth of microbiome research has led to the development of numerous bioinformatics tools and databases, but information about them remains fragmented across disparate, often outdated cataloging efforts, hindering resource discovery and utilization.

To address this critical gap, the [ELIXIR Microbiome Community](https://elixir-europe.org/communities/microbiome) collaborates with the [Research Software Ecosystem](https://research-software-ecosystem.github.io/) to create MiCoReCa (Microbiome Community Resource Catalogue), a comprehensive, dynamic, open-access catalogue of microbiome-related bioinformatics resources:
- Tools from [Research Software Ecosystem Atlas](https://research-software-ecosystem.github.io/RSEc-Atlas/)
- Workflows from [WorkflowHub](https://workflowhub.eu/)
- Training
- Standards
- Databases

Once resources have been extracted, they are filtered using the following decision tree and defined keywords in the [`keywords.yml` file](keywords.yml):

![A flowchart titled "Has EDAM Topics/Operation terms?" begins with a decision point. If "Yes," it leads to "Has the defined terms?" If "No," it leads to "Has the defined keywords in the tags or keywords?" From "Has the defined terms?," "Yes" leads to "MiCoReCa resource," and "No" leads to "Has the defined keywords in the tags or keywords?" From "Has the defined keywords in the tags or keywords?," "Yes" leads to "MiCoReCa resource," and "No" leads to "Has the defined keywords in the description?" From "Has the defined keywords in the description?," "Yes" leads to "MiCoReCa resource," and "No" leads to "Not a MiCoReCa resource."](doc/decision_tree.png)

# Prepare environment

- Install virtualenv (if not already there)

    ```
    $ python3 -m pip install --user virtualenv
    ```

- Create virtual environment

    ```
    $ python3 -m venv env
    ```

- Activate virtual environment

    ```
    $ source env/bin/activate
    ```

- Install requirements

    ```
    $ python3 -m pip install -r requirements.txt
    ```



